import { redirect } from "next/navigation";

interface StaticPageProps {
  params: Promise<{
    slug: string;
  }>;
}

export default async function StaticPageDetail({ params }: StaticPageProps) {
  const { slug } = await params;
  redirect(`/p/${encodeURIComponent(slug)}`);
}
