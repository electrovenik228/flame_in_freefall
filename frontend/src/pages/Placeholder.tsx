import { EmptyState, PageHeader } from "@/components/ui";

export default function Placeholder({ title, step }: { title: string; step: string }) {
  return (
    <>
      <PageHeader title={title} />
      <EmptyState title="This page is not built yet">It arrives with {step} of the build plan.</EmptyState>
    </>
  );
}
