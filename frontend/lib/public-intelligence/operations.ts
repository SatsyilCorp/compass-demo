import type {
  PublicAcquisitionList,
  PublicAcquisitionRecord,
} from "@/lib/api";

export type PublicRecordProjection = {
  run: PublicAcquisitionRecord;
  record: NonNullable<PublicAcquisitionRecord["record_preview"]>[number];
  prediction: NonNullable<PublicAcquisitionRecord["classification_summary"]>["preview"][number] | null;
  flagged: boolean;
};

export function latestAcceptedPublicRuns(
  acquisitions: PublicAcquisitionRecord[],
): PublicAcquisitionRecord[] {
  const seen = new Set<string>();
  const output: PublicAcquisitionRecord[] = [];
  for (const run of acquisitions) {
    if (
      run.status !== "completed" ||
      run.evidence_class !== "public-observed" ||
      seen.has(run.source_id)
    ) continue;
    seen.add(run.source_id);
    output.push(run);
  }
  return output;
}

export function projectPublicRecords(
  acquisitions: PublicAcquisitionRecord[],
): PublicRecordProjection[] {
  const output: PublicRecordProjection[] = [];
  for (const run of latestAcceptedPublicRuns(acquisitions)) {
    const predictions = new Map(
      (run.classification_summary?.preview ?? []).map((prediction) => [
        prediction.source_record_id,
        prediction,
      ]),
    );
    const flags = new Set((run.review_flags ?? []).map((flag) => flag.source_record_id));
    for (const record of run.record_preview ?? []) {
      const prediction = predictions.get(record.source_record_id) ?? null;
      output.push({
        run,
        record,
        prediction,
        flagged: flags.has(record.source_record_id) || Boolean(prediction?.review_required),
      });
    }
  }
  return output;
}

export function publicOperationsSummary(data: PublicAcquisitionList | null) {
  const latest = latestAcceptedPublicRuns(data?.acquisitions ?? []);
  const records = projectPublicRecords(data?.acquisitions ?? []);
  const observedFunding = records.reduce(
    (sum, item) => sum + (item.record.award_amount_usd ?? 0),
    0,
  );
  const classificationReceipts = latest.filter((run) => run.classification_summary);
  return {
    latest,
    records,
    acceptedRecords: latest.reduce((sum, run) => sum + (run.record_count ?? 0), 0),
    observedFunding,
    changedRecords: latest.reduce(
      (sum, run) => sum + (run.added_records ?? 0) + (run.changed_records ?? 0),
      0,
    ),
    reviewFlags: latest.reduce((sum, run) => sum + (run.review_flag_count ?? 0), 0),
    classificationReceipts,
    classifiedRecords: classificationReceipts.reduce(
      (sum, run) => sum + (run.classification_summary?.record_count ?? 0),
      0,
    ),
    healthySources: (data?.source_health ?? []).filter((source) => source.status === "healthy").length,
  };
}

export function publicSourceLabel(run: PublicAcquisitionRecord): string {
  return run.source_label ?? run.source_id;
}

export function publicRecordTitle(
  record: NonNullable<PublicAcquisitionRecord["record_preview"]>[number],
): string {
  return record.title ?? record.recipient_name ?? record.source_record_id;
}

export function formatPublicMoney(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}
