import { Header } from "@/components/Header";
import { PageViewer } from "@/components/PageViewer";

export default function SourcePage({ params, searchParams }: { params: { id: string }; searchParams: { page?: string } }) {
  const page = Math.max(1, Number(searchParams.page ?? "1") || 1);
  return (
    <>
      <Header />
      <PageViewer sourceId={params.id} initialPage={page} />
    </>
  );
}
