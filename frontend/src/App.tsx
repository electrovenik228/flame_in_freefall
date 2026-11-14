import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { AppShell } from "@/components/AppShell";
import { EmptyState, Skeleton } from "@/components/ui";
import Placeholder from "@/pages/Placeholder";

// JavaScript is split per page (section 11).
const Investigations = lazy(() => import("@/pages/Investigations"));
const InvestigationDetail = lazy(() => import("@/pages/InvestigationDetail"));

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 60_000, refetchOnWindowFocus: false } } });
const page = (element: React.ReactNode) => <Suspense fallback={<Skeleton className="h-64" />}>{element}</Suspense>;

const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <Placeholder title="Overview" step="step 8" /> },
      { path: "/investigations", element: page(<Investigations />) },
      { path: "/investigations/:psiId", element: page(<InvestigationDetail />) },
      { path: "/ranking", element: <Placeholder title="Environment ranking" step="step 7" /> },
      { path: "/coverage", element: <Placeholder title="Coverage and gaps" step="step 7" /> },
      { path: "/assistant", element: <Placeholder title="Research assistant" step="step 8" /> },
      { path: "/about", element: <Placeholder title="About and method" step="step 8" /> },
      { path: "*", element: <EmptyState title="Page not found">Use the menu to pick a page.</EmptyState> },
    ],
  },
]);

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
