/** Procedure endpoints. Thin, typed wrappers over the HTTP client. */

import { http } from "./client";
import type { PaginatedResponse } from "@/types/api";
import type {
  ApprovalCreatePayload,
  ApprovalRead,
  DraftUpdatePayload,
  ProcedureListItem,
  ProcedurePublishResponse,
  ProcedureRead,
  ProcedureStatus,
  ProcedureVersionRead,
} from "@/types/procedure";

export interface ListProceduresParams {
  status?: ProcedureStatus;
  search?: string;
  page?: number;
  page_size?: number;
}

export const proceduresApi = {
  async list(
    params: ListProceduresParams = {},
  ): Promise<PaginatedResponse<ProcedureListItem>> {
    const { data } = await http.get<PaginatedResponse<ProcedureListItem>>(
      "/v1/procedures",
      { params },
    );
    return data;
  },

  async get(procedureId: string): Promise<ProcedureRead> {
    const { data } = await http.get<ProcedureRead>(`/v1/procedures/${procedureId}`);
    return data;
  },

  async updateDraft(
    procedureId: string,
    payload: DraftUpdatePayload,
  ): Promise<ProcedureVersionRead> {
    const { data } = await http.patch<ProcedureVersionRead>(
      `/v1/procedures/${procedureId}/draft`,
      payload,
    );
    return data;
  },

  async approve(
    procedureId: string,
    versionId: string,
    payload: ApprovalCreatePayload,
  ): Promise<ApprovalRead> {
    const { data } = await http.post<ApprovalRead>(
      `/v1/procedures/${procedureId}/versions/${versionId}/approve`,
      payload,
    );
    return data;
  },

  async publish(procedureId: string, versionId: string): Promise<ProcedurePublishResponse> {
    const { data } = await http.post<ProcedurePublishResponse>(
      `/v1/procedures/${procedureId}/versions/${versionId}/publish`,
      {},
    );
    return data;
  },

  async resolveClarification(
    procedureId: string,
    payload: {
      clarification_id: string;
      answer: string;
      rationale?: string;
      answer_complete?: boolean;
      affected_steps_reviewed?: boolean;
      step_id?: string;
    },
  ): Promise<ProcedureVersionRead> {
    const { data } = await http.post<ProcedureVersionRead>(
      `/v1/procedures/${procedureId}/resolve-clarification`,
      payload,
    );
    return data;
  },

  async archive(procedureId: string): Promise<void> {
    await http.delete(`/v1/procedures/${procedureId}`);
  },
};
