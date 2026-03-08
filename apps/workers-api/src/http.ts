import type { ProblemDetails, ValidationProblemDetails } from "@board-enthusiasts/migration-contract";

export class ApiError extends Error {
  status: number;
  payload: ProblemDetails | ValidationProblemDetails;

  constructor(status: number, payload: ProblemDetails | ValidationProblemDetails) {
    super(payload.title);
    this.status = status;
    this.payload = payload;
  }
}

export function json(data: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(data, null, 2), {
    headers: {
      "content-type": "application/json; charset=utf-8"
    },
    ...init
  });
}

export function empty(status = 204): Response {
  return new Response(null, { status });
}

export function problem(
  status: number,
  code: string,
  title: string,
  detail: string,
  type = `https://boardtpl.dev/problems/${code}`
): ApiError {
  return new ApiError(status, {
    type,
    title,
    status,
    detail,
    code
  });
}

export function validationProblem(errors: Record<string, string[]>, title = "One or more validation errors occurred."): ApiError {
  return new ApiError(422, {
    title,
    status: 422,
    errors
  });
}
