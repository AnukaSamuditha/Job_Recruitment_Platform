"use client";

import React from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { X } from "lucide-react";
import TiptapEditor from "@/components/editor/TiptapEditor";

const jobSchema = z.object({
  title: z.string().min(3, "Title is required"),
  company: z.string().min(2, "Company is required"),
  description: z.string().min(10, "Description is required"),
});

type JobForm = z.infer<typeof jobSchema>;

export default function CreateJobModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<JobForm>({ resolver: zodResolver(jobSchema) });

  function onSubmit(data: JobForm) {
    // TODO: replace with mutation using TanStack Query
    console.log("Create job:", data);
    onClose();
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative z-10 w-full max-w-2xl rounded-lg bg-white p-6 shadow-sm dark:bg-[#0b0b0b]">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">Create Job</h3>
          <button aria-label="Close" onClick={onClose} className="rounded p-1 hover:bg-zinc-100">
            <X className="h-5 w-5 text-zinc-600" />
          </button>
        </div>

        <form className="mt-4 space-y-4" onSubmit={handleSubmit(onSubmit)}>
          <div>
            <label className="mb-1 block text-sm font-medium">Job Title</label>
            <input {...register("title")} className="w-full rounded border px-3 py-2" />
            {errors.title && <p className="mt-1 text-sm text-red-600">{errors.title.message}</p>}
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium">Company</label>
            <input {...register("company")} className="w-full rounded border px-3 py-2" />
            {errors.company && <p className="mt-1 text-sm text-red-600">{errors.company.message}</p>}
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium">Description</label>
            <TiptapEditor
              value={""}
              onChange={(html) => setValue("description", html, { shouldValidate: true })}
            />
            {errors.description && (
              <p className="mt-1 text-sm text-red-600">{errors.description.message}</p>
            )}
          </div>

          <div className="flex justify-end gap-2">
            <button type="button" onClick={onClose} className="rounded-md px-4 py-2">
              Cancel
            </button>
            <button type="submit" className="rounded-md bg-[var(--accent)] px-4 py-2 text-[var(--accent-foreground)]">
              Save Job
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
