"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { jobsApi, BuildsQueryParams } from "@/lib/api";
import { BuildCard } from "./build-card";
import { BuildLogModal } from "./build-log-modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search, ChevronLeft, ChevronRight } from "lucide-react";

const DOCKER_FILTERS = {
  branchType: ["All", "Main", "Daily", "Stage", "Perf", "Onpremperf"],
  target: ["All", "ARM64", "X86_64"],
};

const SERVER_FILTERS = {
  p4Stream: ["All", "Dev-Build-Server", "Main"],
  buildType: ["All", "Store", "Battle", "Guild", "All"],
};

const STATUSES = ["All", "SUCCESS", "FAILURE", "ABORTED", "IN_PROGRESS"];

interface BuildListProps {
  jobId: string;
  jobType: string;
}

export function BuildList({ jobId, jobType }: BuildListProps) {
  const [page, setPage] = useState(1);
  const [filter1, setFilter1] = useState("All"); // branchType or p4Stream
  const [filter2, setFilter2] = useState("All"); // target or buildType
  const [status, setStatus] = useState("All");
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [selectedBuildId, setSelectedBuildId] = useState<number | null>(null);

  const isDockerJob = jobType === "docker";
  const filterConfig = isDockerJob ? DOCKER_FILTERS : SERVER_FILTERS;

  const queryParams: BuildsQueryParams = {
    page,
    limit: 20,
    ...(status !== "All" && { status }),
    ...(search && { search }),
    ...(isDockerJob && filter1 !== "All" && { branchType: filter1 }),
    ...(isDockerJob && filter2 !== "All" && { target: filter2 }),
    ...(!isDockerJob && filter1 !== "All" && { p4Stream: filter1 }),
    ...(!isDockerJob && filter2 !== "All" && { buildType: filter2 }),
  };

  const { data, isLoading, error } = useQuery({
    queryKey: ["builds", jobId, queryParams],
    queryFn: () => jobsApi.getBuilds(jobId, queryParams),
    refetchInterval: 60000,
  });

  const handleSearch = () => {
    setSearch(searchInput);
    setPage(1);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSearch();
    }
  };

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-4">
        <div className="flex-1 flex gap-2">
          <Input
            placeholder="Search by build ID or parameter value..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyPress={handleKeyPress}
            className="flex-1"
          />
          <Button onClick={handleSearch} size="icon">
            <Search className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex gap-2">
          <Select value={filter1} onValueChange={setFilter1}>
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder={isDockerJob ? "Branch Type" : "P4 Stream"} />
            </SelectTrigger>
            <SelectContent>
              {(isDockerJob ? DOCKER_FILTERS.branchType : SERVER_FILTERS.p4Stream).map((type) => (
                <SelectItem key={type} value={type}>
                  {type}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={filter2} onValueChange={setFilter2}>
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder={isDockerJob ? "Target" : "Build Type"} />
            </SelectTrigger>
            <SelectContent>
              {(isDockerJob ? DOCKER_FILTERS.target : SERVER_FILTERS.buildType).map((type) => (
                <SelectItem key={type} value={type}>
                  {type}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              {STATUSES.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Build List */}
      {isLoading && (
        <div className="text-center py-12">
          <p className="text-muted-foreground">Loading builds...</p>
        </div>
      )}

      {error && (
        <div className="text-center py-12">
          <p className="text-destructive">Failed to load builds</p>
        </div>
      )}

      {data && (
        <>
          {data.data.length === 0 ? (
            <div className="text-center py-12 bg-white rounded-lg border">
              <p className="text-muted-foreground">No builds found. Click "Scrape All History" or "Refresh Recent" to load data.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {data.data.map((build) => (
                <BuildCard
                  key={build.id}
                  build={build}
                  onViewLogs={setSelectedBuildId}
                />
              ))}
            </div>
          )}

          {/* Pagination */}
          {data.meta.totalPages > 1 && (
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                Page {data.meta.page} of {data.meta.totalPages} ({data.meta.total} total builds)
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(p => p + 1)}
                  disabled={page >= data.meta.totalPages}
                >
                  Next
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Build Log Modal */}
      {selectedBuildId && (
        <BuildLogModal
          jobId={jobId}
          buildId={selectedBuildId}
          open={selectedBuildId !== null}
          onClose={() => setSelectedBuildId(null)}
        />
      )}
    </div>
  );
}
