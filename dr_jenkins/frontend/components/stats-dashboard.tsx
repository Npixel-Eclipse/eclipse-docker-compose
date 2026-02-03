"use client";

import { useQuery } from "@tanstack/react-query";
import { statsApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { Loader2, TrendingUp, Clock, CheckCircle, XCircle } from "lucide-react";

const COLORS = {
  success: "#22c55e",
  failure: "#ef4444",
  aborted: "#eab308",
  Main: "#3b82f6",
  Daily: "#8b5cf6",
  Stage: "#ec4899",
  Perf: "#f97316",
  Onpremperf: "#14b8a6",
};

interface StatsDashboardProps {
  jobId: string;
}

export function StatsDashboard({ jobId }: StatsDashboardProps) {
  const { data: overallStats, isLoading: overallLoading } = useQuery({
    queryKey: ["stats-overall", jobId],
    queryFn: () => statsApi.getOverallStats(jobId),
  });

  const { data: branchStats, isLoading: branchLoading } = useQuery({
    queryKey: ["stats-branch-types", jobId],
    queryFn: () => statsApi.getBranchTypeStats(jobId),
  });

  const { data: dailyStats, isLoading: dailyLoading } = useQuery({
    queryKey: ["stats-daily", jobId],
    queryFn: () => statsApi.getDailyStats(jobId, 30),
  });

  const { data: durationTrend, isLoading: durationLoading } = useQuery({
    queryKey: ["stats-duration", jobId],
    queryFn: () => statsApi.getDurationTrend(jobId, 100),
  });

  if (overallLoading || branchLoading || dailyLoading || durationLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  const pieData = overallStats
    ? [
        { name: "Success", value: overallStats.success, color: COLORS.success },
        { name: "Failure", value: overallStats.failure, color: COLORS.failure },
        { name: "Aborted", value: overallStats.aborted, color: COLORS.aborted },
      ]
    : [];

  return (
    <div className="space-y-6">
      {/* Overall Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Builds</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{overallStats?.total || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {overallStats?.successRate.toFixed(1)}%
            </div>
            <p className="text-xs text-muted-foreground">
              {overallStats?.success} successful builds
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Failure Rate</CardTitle>
            <XCircle className="h-4 w-4 text-red-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {overallStats?.failureRate.toFixed(1)}%
            </div>
            <p className="text-xs text-muted-foreground">
              {overallStats?.failure} failed builds
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Duration</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {Math.floor((overallStats?.averageDuration || 0) / 60000)}m
            </div>
            <p className="text-xs text-muted-foreground">
              {Math.floor((overallStats?.averageDuration || 0) / 1000)}s total
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 1 */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Success/Failure Pie Chart */}
        <Card>
          <CardHeader>
            <CardTitle>Build Status Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) =>
                    `${name}: ${(percent * 100).toFixed(0)}%`
                  }
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Branch Type Stats */}
        <Card>
          <CardHeader>
            <CardTitle>Success Rate by Branch Type</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={branchStats}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="branchType" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="successRate" fill="#22c55e" name="Success Rate (%)" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 2 */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Daily Builds Trend */}
        <Card>
          <CardHeader>
            <CardTitle>Daily Build Count (Last 30 Days)</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={dailyStats}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="total" stroke="#8b5cf6" name="Total" />
                <Line type="monotone" dataKey="success" stroke="#22c55e" name="Success" />
                <Line type="monotone" dataKey="failure" stroke="#ef4444" name="Failure" />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Build Duration Trend */}
        <Card>
          <CardHeader>
            <CardTitle>Build Duration Trend (Last 100 Builds)</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={durationTrend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="id" />
                <YAxis tickFormatter={(value) => `${Math.floor(value / 60000)}m`} />
                <Tooltip
                  formatter={(value: number) =>
                    `${Math.floor(value / 60000)}m ${Math.floor((value % 60000) / 1000)}s`
                  }
                />
                <Line
                  type="monotone"
                  dataKey="duration"
                  stroke="#3b82f6"
                  name="Duration"
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Branch Type Details Table */}
      <Card>
        <CardHeader>
          <CardTitle>Branch Type Details</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 px-4">Branch Type</th>
                  <th className="text-right py-2 px-4">Total</th>
                  <th className="text-right py-2 px-4">Success</th>
                  <th className="text-right py-2 px-4">Failure</th>
                  <th className="text-right py-2 px-4">Success Rate</th>
                </tr>
              </thead>
              <tbody>
                {branchStats?.map((stat: any) => (
                  <tr key={stat.branchType} className="border-b">
                    <td className="py-2 px-4 font-medium">{stat.branchType}</td>
                    <td className="text-right py-2 px-4">{stat.total}</td>
                    <td className="text-right py-2 px-4 text-green-600">{stat.success}</td>
                    <td className="text-right py-2 px-4 text-red-600">{stat.failure}</td>
                    <td className="text-right py-2 px-4">{stat.successRate.toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
