"use client";

import { useQuery } from "@tanstack/react-query";
import { jobsApi, JobStatusItem } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, Clock, User, AlertCircle, ExternalLink } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { formatDuration } from "@/lib/utils";

interface StatusDashboardProps {
  jobId: string;
}

function getStatusColor(status: string) {
  switch (status) {
    case "SUCCESS":
      return "bg-green-100 text-green-800 border-green-300";
    case "FAILURE":
      return "bg-red-100 text-red-800 border-red-300";
    case "UNSTABLE":
      return "bg-yellow-100 text-yellow-800 border-yellow-300";
    case "ABORTED":
      return "bg-gray-100 text-gray-800 border-gray-300";
    case "IN_PROGRESS":
      return "bg-blue-100 text-blue-800 border-blue-300";
    default:
      return "bg-gray-100 text-gray-800 border-gray-300";
  }
}

export function StatusDashboard({ jobId }: StatusDashboardProps) {
  const { data: statusItems, isLoading, error } = useQuery({
    queryKey: ["job-status", jobId],
    queryFn: () => jobsApi.getStatus(jobId),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-destructive">Failed to load build status</p>
      </div>
    );
  }

  if (!statusItems || statusItems.length === 0) {
    return (
      <div className="text-center py-12 bg-white rounded-lg border">
        <p className="text-muted-foreground">No build status available. Run "Scrape All History" to load data.</p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {statusItems.map((item) => (
        <StatusCard key={item.type} item={item} />
      ))}
    </div>
  );
}

function StatusCard({ item }: { item: JobStatusItem }) {
  const { type, latestBuild } = item;

  if (!latestBuild) {
    return (
      <Card className="bg-gray-50">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold">{type}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No builds yet</p>
        </CardContent>
      </Card>
    );
  }

  const statusColor = getStatusColor(latestBuild.status);

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-semibold">{type}</CardTitle>
          <Badge className={`${statusColor} border`}>
            {latestBuild.status}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {/* Build Number & Link */}
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Build #{latestBuild.id}</span>
          <a
            href={latestBuild.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:text-blue-800"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </div>

        {/* Time Ago */}
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Clock className="h-3.5 w-3.5" />
          <span>{formatDistanceToNow(new Date(latestBuild.timestamp), { addSuffix: true })}</span>
        </div>

        {/* Duration */}
        {latestBuild.duration && (
          <div className="text-xs text-muted-foreground">
            Duration: {formatDuration(latestBuild.duration)}
          </div>
        )}

        {/* Last User */}
        {latestBuild.userName && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <User className="h-3.5 w-3.5" />
            <span>{latestBuild.userName}</span>
          </div>
        )}

        {/* Broken By (if UNSTABLE or FAILURE) */}
        {latestBuild.brokenBy && (
          <div className="flex items-center gap-1.5 text-xs text-red-600 bg-red-50 p-2 rounded mt-2">
            <AlertCircle className="h-3.5 w-3.5" />
            <span className="font-medium">Broken by: {latestBuild.brokenBy}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
