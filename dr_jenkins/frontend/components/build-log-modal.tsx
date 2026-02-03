"use client";

import { useQuery } from "@tanstack/react-query";
import { jobsApi } from "@/lib/api";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { getStatusColor, formatDuration } from "@/lib/utils";
import { format } from "date-fns";
import { Loader2 } from "lucide-react";

interface BuildLogModalProps {
  jobId: string;
  buildId: number;
  open: boolean;
  onClose: () => void;
}

export function BuildLogModal({ jobId, buildId, open, onClose }: BuildLogModalProps) {
  const { data: build, isLoading: buildLoading } = useQuery({
    queryKey: ["build", jobId, buildId],
    queryFn: () => jobsApi.getBuild(jobId, buildId),
    enabled: open,
  });

  const { data: logsData, isLoading: logsLoading } = useQuery({
    queryKey: ["build-logs", jobId, buildId],
    queryFn: () => jobsApi.getBuildLogs(jobId, buildId),
    enabled: open,
  });

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-6xl max-h-[90vh] flex flex-col">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <DialogTitle>Build #{buildId}</DialogTitle>
            {build && (
              <div className="flex items-center gap-2">
                <Badge className={getStatusColor(build.status)}>
                  {build.status}
                </Badge>
                <span className="text-sm text-muted-foreground">
                  {formatDuration(build.duration)}
                </span>
              </div>
            )}
          </div>
        </DialogHeader>

        {buildLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : build ? (
          <div className="space-y-4 flex-1 overflow-auto">
            {/* Build Info */}
            <div className="space-y-2">
              <div className="text-sm">
                <span className="text-muted-foreground">Timestamp: </span>
                <span>{format(new Date(build.timestamp), "PPp")}</span>
              </div>
              <div className="text-sm">
                <span className="text-muted-foreground">URL: </span>
                <a
                  href={build.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline"
                >
                  {build.url}
                </a>
              </div>
            </div>

            {/* Parameters */}
            {build.parameters.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold mb-2">Parameters</h3>
                <div className="flex flex-wrap gap-2">
                  {build.parameters.map((param, idx) => (
                    <Badge key={idx} variant="secondary">
                      {param.name}: {param.value}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Logs */}
            <div>
              <h3 className="text-sm font-semibold mb-2">Console Output</h3>
              {logsLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin" />
                  <span className="ml-2 text-sm text-muted-foreground">
                    Loading logs...
                  </span>
                </div>
              ) : logsData?.logs ? (
                <pre className="bg-black text-green-400 p-4 rounded-md text-xs overflow-auto max-h-96 font-mono">
                  {logsData.logs}
                </pre>
              ) : (
                <p className="text-sm text-muted-foreground">No logs available</p>
              )}
            </div>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
