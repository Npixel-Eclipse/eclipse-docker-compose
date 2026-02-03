import { Injectable } from '@nestjs/common';
import { PrismaService } from '../database/prisma.service';

export interface StatsQueryParams {
  branchType?: string;
  startDate?: string;
  endDate?: string;
}

@Injectable()
export class StatsService {
  constructor(private prisma: PrismaService) {}

  async getOverallStats(params: StatsQueryParams) {
    const { branchType, startDate, endDate } = params;

    const where: any = {};

    if (startDate || endDate) {
      where.timestamp = {};
      if (startDate) where.timestamp.gte = new Date(startDate);
      if (endDate) where.timestamp.lte = new Date(endDate);
    }

    if (branchType) {
      where.parameters = {
        some: {
          name: 'BRANCH_TYPE',
          value: branchType,
        },
      };
    }

    const [total, success, failure, aborted, avgDuration] = await Promise.all([
      this.prisma.dockerBuild.count({ where }),
      this.prisma.dockerBuild.count({ where: { ...where, status: 'SUCCESS' } }),
      this.prisma.dockerBuild.count({ where: { ...where, status: 'FAILURE' } }),
      this.prisma.dockerBuild.count({ where: { ...where, status: 'ABORTED' } }),
      this.prisma.dockerBuild.aggregate({
        where: { ...where, duration: { not: null } },
        _avg: { duration: true },
      }),
    ]);

    return {
      total,
      success,
      failure,
      aborted,
      successRate: total > 0 ? (success / total) * 100 : 0,
      failureRate: total > 0 ? (failure / total) * 100 : 0,
      averageDuration: avgDuration._avg.duration || 0,
    };
  }

  async getBranchTypeStats() {
    const branchTypes = ['Main', 'Daily', 'Stage', 'Perf', 'Onpremperf'];
    const stats = [];

    for (const branchType of branchTypes) {
      const buildIds = await this.prisma.dockerBuildParameter.findMany({
        where: {
          name: 'BRANCH_TYPE',
          value: branchType,
        },
        select: { dockerBuildId: true },
      });

      const buildIdList = buildIds.map(b => b.dockerBuildId);

      if (buildIdList.length === 0) {
        stats.push({
          branchType,
          total: 0,
          success: 0,
          failure: 0,
          successRate: 0,
        });
        continue;
      }

      const [total, success, failure] = await Promise.all([
        this.prisma.dockerBuild.count({
          where: { id: { in: buildIdList } },
        }),
        this.prisma.dockerBuild.count({
          where: { id: { in: buildIdList }, status: 'SUCCESS' },
        }),
        this.prisma.dockerBuild.count({
          where: { id: { in: buildIdList }, status: 'FAILURE' },
        }),
      ]);

      stats.push({
        branchType,
        total,
        success,
        failure,
        successRate: total > 0 ? (success / total) * 100 : 0,
      });
    }

    return stats;
  }

  async getDailyStats(days: number = 30) {
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - days);

    const builds = await this.prisma.dockerBuild.findMany({
      where: {
        timestamp: {
          gte: startDate,
        },
      },
      select: {
        timestamp: true,
        status: true,
        duration: true,
      },
      orderBy: {
        timestamp: 'asc',
      },
    });

    // Group by date
    const dailyMap = new Map<string, { total: number; success: number; failure: number; totalDuration: number }>();

    builds.forEach(build => {
      const dateKey = build.timestamp.toISOString().split('T')[0];
      if (!dailyMap.has(dateKey)) {
        dailyMap.set(dateKey, { total: 0, success: 0, failure: 0, totalDuration: 0 });
      }

      const stats = dailyMap.get(dateKey);
      stats.total++;
      if (build.status === 'SUCCESS') stats.success++;
      if (build.status === 'FAILURE') stats.failure++;
      if (build.duration) stats.totalDuration += build.duration;
    });

    const dailyStats = Array.from(dailyMap.entries()).map(([date, stats]) => ({
      date,
      total: stats.total,
      success: stats.success,
      failure: stats.failure,
      successRate: stats.total > 0 ? (stats.success / stats.total) * 100 : 0,
      averageDuration: stats.total > 0 ? stats.totalDuration / stats.total : 0,
    }));

    return dailyStats;
  }

  async getBuildDurationTrend(limit: number = 100) {
    const builds = await this.prisma.dockerBuild.findMany({
      where: {
        duration: { not: null },
      },
      select: {
        id: true,
        timestamp: true,
        duration: true,
        status: true,
      },
      orderBy: {
        id: 'desc',
      },
      take: limit,
    });

    return builds.reverse();
  }
}
