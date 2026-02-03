import { Injectable } from '@nestjs/common';
import { PrismaService } from '../database/prisma.service';
import { Prisma } from '@prisma/client';

export interface BuildsQueryParams {
  page?: number;
  limit?: number;
  branchType?: string;
  status?: string;
  search?: string;
}

@Injectable()
export class BuildsService {
  constructor(private prisma: PrismaService) {}

  async getBuilds(params: BuildsQueryParams) {
    const {
      page = 1,
      limit = 50,
      branchType,
      status,
      search,
    } = params;

    const skip = (page - 1) * limit;

    // Build where clause
    const where: Prisma.DockerBuildWhereInput = {};

    if (status) {
      where.status = status;
    }

    if (branchType) {
      where.parameters = {
        some: {
          name: 'BRANCH_TYPE',
          value: branchType,
        },
      };
    }

    if (search) {
      where.OR = [
        {
          id: isNaN(Number(search)) ? undefined : Number(search),
        },
        {
          parameters: {
            some: {
              value: {
                contains: search,
                mode: 'insensitive',
              },
            },
          },
        },
      ];
    }

    const [builds, total] = await Promise.all([
      this.prisma.dockerBuild.findMany({
        where,
        include: {
          parameters: true,
        },
        orderBy: {
          id: 'desc',
        },
        skip,
        take: limit,
      }),
      this.prisma.dockerBuild.count({ where }),
    ]);

    return {
      data: builds,
      meta: {
        total,
        page,
        limit,
        totalPages: Math.ceil(total / limit),
      },
    };
  }

  async getBuildById(id: number) {
    return this.prisma.dockerBuild.findUnique({
      where: { id },
      include: {
        parameters: true,
      },
    });
  }

  async getBuildLogs(id: number) {
    const build = await this.prisma.dockerBuild.findUnique({
      where: { id },
      select: {
        logs: true,
      },
    });

    return build?.logs || '';
  }

  async getBuildStats() {
    const totalBuilds = await this.prisma.dockerBuild.count();

    const successCount = await this.prisma.dockerBuild.count({
      where: { status: 'SUCCESS' },
    });

    const failureCount = await this.prisma.dockerBuild.count({
      where: { status: 'FAILURE' },
    });

    const avgDuration = await this.prisma.dockerBuild.aggregate({
      _avg: {
        duration: true,
      },
      where: {
        duration: {
          not: null,
        },
      },
    });

    return {
      totalBuilds,
      successCount,
      failureCount,
      successRate: totalBuilds > 0 ? (successCount / totalBuilds) * 100 : 0,
      averageDuration: avgDuration._avg.duration || 0,
    };
  }
}
