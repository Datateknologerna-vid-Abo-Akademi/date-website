import { notFound, redirect } from "next/navigation";

import { getArchivePictureCollectionById } from "@/lib/api/queries";

interface ArchivePictureByIdPageProps {
  params: {
    id: string;
  };
}

export default async function ArchivePictureByIdPage({ params }: ArchivePictureByIdPageProps) {
  const collectionId = Number(params.id);
  if (Number.isNaN(collectionId)) notFound();

  const payload = await getArchivePictureCollectionById(collectionId).catch(() => null);
  if (!payload) notFound();

  redirect(`/archive/pictures/${payload.year}/${encodeURIComponent(payload.album)}`);
}
