import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:4000";

export const api = axios.create({
  baseURL: API_URL,
});

export interface Build {
  id: number;
  status: string;
  duration: number | null;
  timestamp: string;
  url: string;
  userName?: string;
  imageTag?: string;
  parameters: Parameter[];
  logs?: string;
  createdAt: string;
  updatedAt: string;
}

export interface Parameter {
  id: number;
  buildId: number;
  name: string;
  value: string;
}

export interface BuildsResponse {
  data: Build[];
  meta: {
    total: number;
    page: number;
    limit: number;
    totalPages: number;
  };
}

export interface BuildsQueryParams {
  page?: number;
  limit?: number;
  branchType?: string;
  status?: string;
  search?: string;
}

export const buildsApi = {
  getBuilds: async (params?: BuildsQueryParams): Promise<BuildsResponse> => {
    const response = await api.get("/api/builds", { params });
    return response.data;
  },

  getBuild: async (id: number): Promise<Build> => {
    const response = await api.get(`/api/builds/${id}`);
    return response.data;
  },

  getBuildLogs: async (id: number): Promise<{ buildId: number; logs: string }> => {
    const response = await api.get(`/api/builds/${id}/logs`);
    return response.data;
  },

  getStats: async (): Promise<any> => {
    const response = await api.get("/api/builds/stats");
    return response.data;
  },
};

// New Jobs API
export interface Job {
  id: string;
  name: string;
  jenkinsPath: string;
  displayName: string;
  type: string;
  description?: string;
  parameters: string[];
  tags: {
    display: string[];
    filters: string[];
  };
}

export interface JobStatusItem {
  type: string;
  latestBuild: {
    id: number;
    status: string;
    userName?: string;
    timestamp: string;
    duration: number | null;
    url: string;
    brokenBy?: string;
  } | null;
}

export const jobsApi = {
  getJobs: async (): Promise<Job[]> => {
    const response = await api.get("/api/jobs");
    return response.data;
  },

  getJob: async (jobId: string): Promise<Job> => {
    const response = await api.get(`/api/jobs/${jobId}`);
    return response.data;
  },

  getBuilds: async (jobId: string, params?: BuildsQueryParams): Promise<BuildsResponse> => {
    const response = await api.get(`/api/jobs/${jobId}/builds`, { params });
    return response.data;
  },

  getBuild: async (jobId: string, buildId: number): Promise<Build> => {
    const response = await api.get(`/api/jobs/${jobId}/builds/${buildId}`);
    return response.data;
  },

  getBuildLogs: async (jobId: string, buildId: number): Promise<{ buildId: number; logs: string }> => {
    const response = await api.get(`/api/jobs/${jobId}/builds/${buildId}/logs`);
    return response.data;
  },

  getStats: async (jobId: string): Promise<any> => {
    const response = await api.get(`/api/jobs/${jobId}/stats`);
    return response.data;
  },

  getStatus: async (jobId: string): Promise<JobStatusItem[]> => {
    const response = await api.get(`/api/jobs/${jobId}/status`);
    return response.data;
  },
};

export const statsApi = {
  getOverallStats: async (jobId: string, params?: any): Promise<any> => {
    const response = await api.get(`/api/jobs/${jobId}/stats/overall`, { params });
    return response.data;
  },

  getBranchTypeStats: async (jobId: string): Promise<any> => {
    const response = await api.get(`/api/jobs/${jobId}/stats/branch-types`);
    return response.data;
  },

  getDailyStats: async (jobId: string, days: number = 30): Promise<any> => {
    const response = await api.get(`/api/jobs/${jobId}/stats/daily`, { params: { days } });
    return response.data;
  },

  getDurationTrend: async (jobId: string, limit: number = 100): Promise<any> => {
    const response = await api.get(`/api/jobs/${jobId}/stats/duration-trend`, { params: { limit } });
    return response.data;
  },
};

export const scrapeApi = {
  scrapeInitial: async (jobId?: string): Promise<void> => {
    if (jobId) {
      await api.post(`/api/jobs/${jobId}/scrape/initial`);
    } else {
      await api.post("/api/scrape/initial");
    }
  },

  scrapeRecent: async (jobId?: string): Promise<void> => {
    if (jobId) {
      await api.post(`/api/jobs/${jobId}/scrape/recent`);
    } else {
      await api.post("/api/scrape/recent");
    }
  },
};
