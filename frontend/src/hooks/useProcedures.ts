/** Query + mutation hooks for procedures. */

import {
  useMutation,
  useQuery,
  useQueryClient,
  keepPreviousData,
} from "@tanstack/react-query";
import { proceduresApi, type ListProceduresParams } from "@/api/procedures";
import type {
  ApprovalCreatePayload,
  DraftUpdatePayload,
} from "@/types/procedure";

export const procedureKeys = {
  all: ["procedures"] as const,
  list: (params: ListProceduresParams) =>
    [...procedureKeys.all, "list", params] as const,
  detail: (id: string) => [...procedureKeys.all, "detail", id] as const,
};

export function useProcedureList(params: ListProceduresParams) {
  return useQuery({
    queryKey: procedureKeys.list(params),
    queryFn: () => proceduresApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useProcedure(id: string | undefined) {
  return useQuery({
    queryKey: procedureKeys.detail(id ?? "none"),
    queryFn: () => proceduresApi.get(id as string),
    enabled: Boolean(id),
  });
}

export function useUpdateDraft(procedureId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: DraftUpdatePayload) =>
      proceduresApi.updateDraft(procedureId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: procedureKeys.detail(procedureId) });
      qc.invalidateQueries({ queryKey: procedureKeys.all });
    },
  });
}

export function useApproveProcedure(procedureId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ApprovalCreatePayload) =>
      proceduresApi.approve(procedureId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: procedureKeys.detail(procedureId) });
      qc.invalidateQueries({ queryKey: procedureKeys.all });
    },
  });
}

export function usePublishProcedure(procedureId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => proceduresApi.publish(procedureId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: procedureKeys.detail(procedureId) });
      qc.invalidateQueries({ queryKey: procedureKeys.all });
    },
  });
}
