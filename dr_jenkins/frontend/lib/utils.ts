import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDuration(ms: number | null): string {
  if (!ms) return "N/A";

  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);

  if (hours > 0) {
    return `${hours}h ${minutes % 60}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`;
  }
  return `${seconds}s`;
}

export function getStatusColor(status: string): string {
  switch (status) {
    case "SUCCESS":
      return "bg-green-500";
    case "FAILURE":
      return "bg-red-500";
    case "ABORTED":
      return "bg-yellow-500";
    case "IN_PROGRESS":
      return "bg-blue-500";
    default:
      return "bg-gray-500";
  }
}

export function getStatusTextColor(status: string): string {
  switch (status) {
    case "SUCCESS":
      return "text-green-600";
    case "FAILURE":
      return "text-red-600";
    case "ABORTED":
      return "text-yellow-600";
    case "IN_PROGRESS":
      return "text-blue-600";
    default:
      return "text-gray-600";
  }
}
