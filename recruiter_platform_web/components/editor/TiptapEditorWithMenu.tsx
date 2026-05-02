"use client";

import React from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import { Bold, Italic, Underline as UIcon, List, ListOrdered } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const headingLevels = [1, 2, 3] as const;

export default function TiptapEditorWithMenu({
  value,
  onChange,
}: {
  value?: string;
  onChange: (html: string) => void;
}) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      Underline,
    ],
    content: value || "",
    editorProps: {
      attributes: {
        class:
          "prose prose-sm max-w-none dark:prose-invert focus:outline-none min-h-[200px] px-1 py-1 [&_h1]:text-2xl [&_h1]:font-semibold [&_h1]:tracking-tight [&_h2]:text-xl [&_h2]:font-semibold [&_h3]:text-lg [&_h3]:font-semibold",
      },
    },
    onUpdate: ({ editor: ed }) => onChange(ed.getHTML()),
  });

  const toolbarBtn = (active: boolean) =>
    cn(
      "h-8 min-w-8 px-2",
      active && "bg-muted text-foreground border-border",
    );

  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        <div className="flex flex-wrap gap-1 border-b border-border/60 pb-3">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className={toolbarBtn(editor?.isActive("bold") ?? false)}
            onClick={() => editor?.chain().focus().toggleBold().run()}
            aria-label="Bold"
          >
            <Bold className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className={toolbarBtn(editor?.isActive("italic") ?? false)}
            onClick={() => editor?.chain().focus().toggleItalic().run()}
            aria-label="Italic"
          >
            <Italic className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className={toolbarBtn(editor?.isActive("underline") ?? false)}
            onClick={() => editor?.chain().focus().toggleUnderline().run()}
            aria-label="Underline"
          >
            <UIcon className="h-4 w-4" />
          </Button>
          <span className="mx-1 hidden h-6 w-px bg-border sm:inline" aria-hidden />
          {headingLevels.map((level) => (
            <Button
              key={level}
              type="button"
              variant="outline"
              size="sm"
              className={toolbarBtn(editor?.isActive("heading", { level }) ?? false)}
              onClick={() => editor?.chain().focus().toggleHeading({ level }).run()}
            >
              H{level}
            </Button>
          ))}
          <span className="mx-1 hidden h-6 w-px bg-border sm:inline" aria-hidden />
          <Button
            type="button"
            variant="outline"
            size="sm"
            className={toolbarBtn(editor?.isActive("bulletList") ?? false)}
            onClick={() => editor?.chain().focus().toggleBulletList().run()}
            aria-label="Bullet list"
          >
            <List className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className={toolbarBtn(editor?.isActive("orderedList") ?? false)}
            onClick={() => editor?.chain().focus().toggleOrderedList().run()}
            aria-label="Numbered list"
          >
            <ListOrdered className="h-4 w-4" />
          </Button>
        </div>
        <div className="rounded-md border border-border/70 bg-background px-3 py-2">
          <EditorContent editor={editor} />
        </div>
      </CardContent>
    </Card>
  );
}
