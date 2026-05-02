import { API_BASE } from "@/lib/api/config";

export type Job = {
  id: string;
  title: string;
  company: string;
  description: string;
  location?: string;
  posted: string;
};

type ApiJob = {
  id: string;
  title: string;
  company: string;
  description_plain: string;
  has_embedding: boolean;
  created_at: string;
};

function mapApiJob(j: ApiJob): Job {
  const created = new Date(j.created_at);
  const posted =
    Number.isNaN(created.getTime()) ? "—" : formatRelative(created);
  return {
    id: j.id,
    title: j.title,
    company: j.company,
    description: j.description_plain,
    posted,
  };
}

function formatRelative(d: Date): string {
  const sec = Math.round((Date.now() - d.getTime()) / 1000);
  if (sec < 60) return "just now";
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 48) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  return `${day}d ago`;
}

async function parseJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export async function getJobs(): Promise<Job[]> {
  const res = await fetch(`${API_BASE}/api/v1/jobs`, { cache: "no-store" });
  const data = await parseJson<ApiJob[]>(res);
  return data.map(mapApiJob);
}

export async function getJob(id: string): Promise<Job | null> {
  const res = await fetch(`${API_BASE}/api/v1/jobs/${id}`, { cache: "no-store" });
  if (res.status === 404) return null;
  const data = await parseJson<ApiJob>(res);
  return mapApiJob(data);
}

export async function createJob(
  job: Omit<Job, "id" | "posted">,
): Promise<Job> {
  const res = await fetch(`${API_BASE}/api/v1/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: job.title,
      company: job.company,
      description_html: job.description,
    }),
  });
  const data = await parseJson<ApiJob>(res);
  return mapApiJob(data);
}

export async function updateJob(
  id: string,
  updates: Partial<Job>,
): Promise<Job | null> {
  const body: Record<string, string> = {};
  if (updates.title != null) body.title = updates.title;
  if (updates.company != null) body.company = updates.company;
  if (updates.description != null) body.description_html = updates.description;
  const res = await fetch(`${API_BASE}/api/v1/jobs/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.status === 404) return null;
  const data = await parseJson<ApiJob>(res);
  return mapApiJob(data);
}

export async function deleteJob(id: string): Promise<boolean> {
  const res = await fetch(`${API_BASE}/api/v1/jobs/${id}`, { method: "DELETE" });
  if (res.status === 204) return true;
  if (!res.ok) return false;
  return true;
}

export type ApiCandidate = {
  id: string;
  display_name: string;
  cv_storage_key: string;
  match_score?: number | null;
  missing_skills?: string[];
};

export async function listJobCandidates(jobId: string): Promise<ApiCandidate[]> {
  const res = await fetch(`${API_BASE}/api/v1/jobs/${jobId}/candidates`, {
    cache: "no-store",
  });
  return parseJson<ApiCandidate[]>(res);
}

export type CandidateCvPreview = {
  pages: string[];
  summary_text: string | null;
  structured_profile: Record<string, unknown> | null;
  screening: Record<string, string> | null;
};

/** CV pages as PNG data URLs plus optional structured summary from the API. */
export async function getCandidateCvPreview(
  jobId: string,
  candidateId: string,
): Promise<CandidateCvPreview> {
  const res = await fetch(
    `${API_BASE}/api/v1/jobs/${jobId}/candidates/${candidateId}/cv-preview`,
    { cache: "no-store" },
  );
  return parseJson<CandidateCvPreview>(res);
}

export type CandidateContact = {
  full_name: string;
  email: string;
  phone: string;
  location: string;
  headline: string;
  summary: string;
};

export type CandidateCvAnalysis = {
  screening_run_id: string | null;
  step_type: string | null;
  recorded_at: string | null;
  skills_count: number | null;
  roles_count: number | null;
  schema_name: string | null;
  detail: string | null;
};

export type CandidateJobScreening = {
  screening_run_id: string | null;
  status: string | null;
  created_at: string | null;
  skill_match: string | null;
  ranking: string | null;
  interview: string | null;
};

export type CandidateJobFit = {
  overall_score: number;
  matched_skills: string[];
  missing_skills: string[];
  summary_line: string;
};

/** Recruiter LLM brief from cv_parser (stored under parse_result.cv_parser_agent). */
export type CvParserAgentPayload = {
  alignment_summary: string[];
  gaps_or_questions: string[];
  risk_flags: string[];
  disclaimer: string;
  error: string | null;
};

/** Full candidate row, CV-derived contact, parse status, and latest job screening text (no raster pages). */
export type CandidateDetail = {
  id: string;
  job_id: string;
  display_name: string;
  cv_storage_key: string;
  created_at: string;
  contact: CandidateContact;
  parse_summary: string | null;
  structured_profile: Record<string, unknown> | null;
  cv_analysis: CandidateCvAnalysis;
  job_screening: CandidateJobScreening;
  job_fit?: CandidateJobFit | null;
  cv_parser_agent?: CvParserAgentPayload | null;
};

export async function getCandidateDetail(
  jobId: string,
  candidateId: string,
): Promise<CandidateDetail> {
  const res = await fetch(
    `${API_BASE}/api/v1/jobs/${jobId}/candidates/${candidateId}`,
    { cache: "no-store" },
  );
  return parseJson<CandidateDetail>(res);
}

export type UploadCvResponse = {
  candidate_id: string;
  cv_storage_key: string;
  screening_run_id: string;
};

export async function uploadCandidateCv(
  jobId: string,
  file: File,
  displayName?: string,
): Promise<UploadCvResponse> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("display_name", displayName ?? file.name.replace(/\.[^/.]+$/, ""));
  const res = await fetch(`${API_BASE}/api/v1/jobs/${jobId}/candidates`, {
    method: "POST",
    body: fd,
  });
  return parseJson(res);
}

/**
 * Upload CV with byte-accurate send progress (`XMLHttpRequest.upload`).
 * The server may take a long time after the body is received (parsing/embeddings); progress reaches 100% when the HTTP response arrives.
 */
export async function uploadCandidateCvWithProgress(
  jobId: string,
  file: File,
  options?: {
    displayName?: string;
    onProgress?: (info: { percent: number; loaded: number; total: number | null }) => void;
  },
): Promise<UploadCvResponse> {
  const displayName = options?.displayName ?? file.name.replace(/\.[^/.]+$/, "");
  const onProgress = options?.onProgress;
  const url = `${API_BASE}/api/v1/jobs/${jobId}/candidates`;

  onProgress?.({ percent: 0, loaded: 0, total: file.size });

  const fd = new FormData();
  fd.append("file", file);
  fd.append("display_name", displayName);

  // #region agent log
  const _dbg = (message: string, data: Record<string, unknown>, hypothesisId: string) => {
    fetch("http://127.0.0.1:7925/ingest/a4a8d503-3acb-41c9-ad31-b49e964e236e", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "2354bc" },
      body: JSON.stringify({
        sessionId: "2354bc",
        hypothesisId,
        location: "jobs.ts:uploadCandidateCvWithProgress",
        message,
        data,
        timestamp: Date.now(),
      }),
    }).catch(() => {});
  };
  // #endregion

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.responseType = "json";

    xhr.upload.onprogress = (ev) => {
      if (!onProgress) return;
      if (ev.lengthComputable && ev.total > 0) {
        const percent = Math.min(100, Math.round((ev.loaded / ev.total) * 100));
        onProgress({ percent, loaded: ev.loaded, total: ev.total });
        // #region agent log
        if (percent === 100 || percent % 25 === 0) {
          _dbg("xhr_upload_progress", { percent, loaded: ev.loaded, total: ev.total }, "H2");
        }
        // #endregion
      } else {
        onProgress({ percent: 0, loaded: ev.loaded, total: null });
      }
    };

    xhr.onload = () => {
      if (xhr.status < 200 || xhr.status >= 300) {
        const text =
          typeof xhr.responseText === "string" && xhr.responseText
            ? xhr.responseText
            : xhr.statusText;
        reject(new Error(text || `HTTP ${xhr.status}`));
        return;
      }
      const body = xhr.response as UploadCvResponse;
      if (!body || typeof body.candidate_id !== "string") {
        reject(new Error("Invalid upload response"));
        return;
      }
      onProgress?.({ percent: 100, loaded: file.size, total: file.size });
      // #region agent log
      _dbg("xhr_upload_complete", { status: xhr.status, candidate_id: body.candidate_id }, "H2");
      // #endregion
      resolve(body);
    };

    xhr.onerror = () => {
      reject(
        new Error(
          "Network error during upload. Check that the API is running and NEXT_PUBLIC_API_URL matches the backend.",
        ),
      );
    };

    xhr.send(fd);
  });
}

export type ScreeningRun = {
  id: string;
  job_id: string;
  status: string;
  created_at: string;
};

export async function startScreeningRun(
  jobId: string,
  candidateIds: string[],
): Promise<ScreeningRun> {
  const res = await fetch(`${API_BASE}/api/v1/jobs/${jobId}/screening-runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ candidate_ids: candidateIds }),
  });
  return parseJson<ScreeningRun>(res);
}
