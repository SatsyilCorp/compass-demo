import {
  getScaleExportApi,
  getScaleProfilesApi,
  getScaleRunApi,
  getScaleRunsApi,
  postScaleExportApi,
  postScalePlanApi,
  postScaleRunApi,
  postScaleRunCancelApi,
} from "@/lib/api";
import type { ScaleAdapter } from "./types";

export const liveScaleAdapter: ScaleAdapter = {
  getProfiles: getScaleProfilesApi,
  previewPlan: postScalePlanApi,
  launchRun: postScaleRunApi,
  listRuns: getScaleRunsApi,
  getRun: getScaleRunApi,
  cancelRun: (runId) => postScaleRunCancelApi(runId, { reason: "operator_requested" }),
  requestExport: postScaleExportApi,
  getExport: getScaleExportApi,
};
