"use client";

import { useParams } from "next/navigation";
import { AdaptiveSection } from "@/components/test/AdaptiveSection";

export default function SectionTestPage() {
  const { formId } = useParams<{ formId: string }>();
  return <AdaptiveSection formId={formId} />;
}
