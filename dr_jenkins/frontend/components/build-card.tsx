"use client";

import { Build } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { formatDuration } from "@/lib/utils";
import { format } from "date-fns";
import { Clock, Calendar } from "lucide-react";

interface BuildCardProps {
  build: Build;
  onViewLogs: (buildId: number) => void;
}

const BRANCH_TYPE_COLORS: Record<string, string> = {
  Main: "bg-purple-100 text-purple-800 border-purple-300",
  Daily: "bg-blue-100 text-blue-800 border-blue-300",
  Stage: "bg-yellow-100 text-yellow-800 border-yellow-300",
  Perf: "bg-orange-100 text-orange-800 border-orange-300",
  Onpremperf: "bg-teal-100 text-teal-800 border-teal-300",
};

const STATUS_COLORS: Record<string, string> = {
  SUCCESS: "bg-green-500 text-white hover:bg-green-600",
  FAILURE: "bg-red-500 text-white hover:bg-red-600",
  ABORTED: "bg-yellow-500 text-white hover:bg-yellow-600",
  IN_PROGRESS: "bg-blue-500 text-white hover:bg-blue-600",
};

export function BuildCard({ build, onViewLogs }: BuildCardProps) {
  // Helper function to find parameter case-insensitively
  const findParam = (name: string) => {
    return build.parameters.find(
      (p) => p.name.toLowerCase() === name.toLowerCase()
    );
  };

  const branchTypeParam = findParam("BRANCH_TYPE");
  const targetParam = findParam("TARGET");
  const noCacheParam = findParam("NO_CACHE");
  const deployParam = findParam("DEPLOY");

  const statusColor = STATUS_COLORS[build.status] || "bg-gray-500 text-white";
  const branchColor = branchTypeParam
    ? BRANCH_TYPE_COLORS[branchTypeParam.value] || "bg-gray-100 text-gray-800 border-gray-300"
    : "";

  return (
    <div
      className="group border rounded-lg p-3 hover:shadow-lg transition-all cursor-pointer bg-white hover:bg-gray-50"
      onClick={() => onViewLogs(build.id)}
    >
      <div className="flex items-center justify-between gap-4">
        {/* Left: Build ID and Status */}
        <div className="flex items-center gap-2">
          <div className="text-base font-bold text-gray-700 min-w-[70px]">
            #{build.id}
          </div>
          <Badge className={`${statusColor} px-2 py-0.5 text-xs font-semibold`}>
            {build.status}
          </Badge>
        </div>

        {/* Center: Tags */}
        <div className="flex items-center gap-2 flex-wrap flex-1">
          {/* BranchType Tag */}
          {branchTypeParam && (
            <Badge
              variant="outline"
              className={`${branchColor} px-2 py-0.5 text-xs font-bold border`}
            >
              {branchTypeParam.value}
            </Badge>
          )}

          {/* User Tag */}
          {build.userName && (
            <Badge
              variant="secondary"
              className="bg-indigo-100 text-indigo-800 text-xs px-2 py-0.5 border border-indigo-200"
            >
              👤 {build.userName}
            </Badge>
          )}

          {/* Image Tag */}
          {build.imageTag && (
            <Badge
              variant="secondary"
              className="bg-gray-100 text-gray-800 text-xs px-2 py-0.5 border border-gray-300 font-mono"
              title={`Docker Image Tag: ${build.imageTag}`}
            >
              🏷️ {build.imageTag}
            </Badge>
          )}

          {/* Target Tag */}
          {targetParam && (
            <Badge
              variant="secondary"
              className="bg-emerald-100 text-emerald-800 text-xs px-2 py-0.5 border border-emerald-200"
            >
              🎯 {targetParam.value}
            </Badge>
          )}

          {/* Deploy Tag */}
          {deployParam && (
            <Badge
              variant="secondary"
              className="bg-cyan-100 text-cyan-800 text-xs px-2 py-0.5 border border-cyan-200"
            >
              🚀 {deployParam.value}
            </Badge>
          )}

          {/* No Cache Tag */}
          {noCacheParam && noCacheParam.value === "true" && (
            <Badge
              variant="secondary"
              className="bg-red-100 text-red-800 text-xs px-2 py-0.5 border border-red-200"
            >
              🚫 CACHE
            </Badge>
          )}
        </div>

        {/* Right: Time Info */}
        <div className="flex items-center gap-3">
          {/* Timestamp */}
          <div className="flex items-center gap-1 text-xs text-gray-600">
            <Calendar className="h-3 w-3" />
            <span>{format(new Date(build.timestamp), "MM/dd HH:mm")}</span>
          </div>

          {/* Duration */}
          <div className="flex items-center gap-1 text-xs text-gray-600 min-w-[50px]">
            <Clock className="h-3 w-3" />
            <span>{formatDuration(build.duration)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
