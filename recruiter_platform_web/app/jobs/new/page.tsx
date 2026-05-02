"use client";

import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import TiptapEditorWithMenu from "@/components/editor/TiptapEditorWithMenu";
import { useCreateJob } from "@/lib/hooks/useJobs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const jobSchema = z.object({
  title: z.string().min(3),
  company: z.string().min(2),
  description: z.string().min(10),
});
type JobForm = z.infer<typeof jobSchema>;

export default function NewJobPage() {
  const router = useRouter();
  const createJobMutation = useCreateJob();
  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<JobForm>({ resolver: zodResolver(jobSchema) });

  async function onSubmit(data: JobForm) {
    await createJobMutation.mutateAsync({
      title: data.title,
      company: data.company,
      description: data.description,
    });
    router.push("/");
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-4 space-y-0">
          <div className="space-y-1">
            <CardDescription>New posting</CardDescription>
            <CardTitle className="text-3xl font-semibold tracking-tight">Create job</CardTitle>
            <p className="text-sm text-muted-foreground">Describe the role and what you are looking for.</p>
          </div>
          <Button variant="outline" asChild>
            <Link href="/">Back to jobs</Link>
          </Button>
        </CardHeader>
      </Card>

      <Card>
        <CardContent className="p-6">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="job-title">Job title</Label>
              <Input id="job-title" {...register("title")} autoComplete="organization-title" />
              {errors.title && <p className="text-sm text-destructive">{String(errors.title.message)}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="job-company">Company</Label>
              <Input id="job-company" {...register("company")} autoComplete="organization" />
              {errors.company && <p className="text-sm text-destructive">{String(errors.company.message)}</p>}
            </div>

            <div className="space-y-2">
              <Label>Description</Label>
              <p className="text-xs text-muted-foreground">Use headings and lists to structure the role.</p>
              <TiptapEditorWithMenu value="" onChange={(html) => setValue("description", html, { shouldValidate: true })} />
              {errors.description && (
                <p className="text-sm text-destructive">{String(errors.description.message)}</p>
              )}
            </div>

            <div className="flex justify-end border-t border-border/60 pt-4">
              <Button type="submit" disabled={createJobMutation.isPending} className="min-w-[120px] rounded-full">
                {createJobMutation.isPending ? "Saving…" : "Save job"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
