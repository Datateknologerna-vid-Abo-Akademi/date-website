import { notFound } from "next/navigation";

import { RichContent } from "@/components/rich-content";
import { getStaticPage } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

interface StaticPageProps {
  params: Promise<{
    slug: string;
  }>;
}

export default async function StaticPageDetail({ params }: StaticPageProps) {
  await ensureModuleEnabled("staticpages");
  const { slug } = await params;
  const page = await getStaticPage(slug).catch(() => null);
  if (!page) {
    notFound();
  }
  return (
    <div className="container-md min-vh-100 container-margin-top p-1">
      <div className="container-size break-words">
        <div className="content">
          <RichContent html={page.content} />
        </div>
      </div>
    </div>
  );
}

