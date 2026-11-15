import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { AppShell } from "@/components/AppShell";
import { EmptyState, Skeleton } from "@/components/ui";

// JavaScript is split per page (section 11).
const Investigations = lazy(() => import("@/pages/Investigations"));
const InvestigationDetail = lazy(() => import("@/pages/InvestigationDetail"));
const Ranking = lazy(() => import("@/pages/Ranking"));
const Coverage = lazy(() => import("@/pages/Coverage"));
const Assistant = lazy(() => import("@/pages/Assistant"));
const Overview = lazy(() => import("@/pages/Overview"));
const About = lazy(() => import("@/pages/About"));

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 60_000, refetchOnWindowFocus: false } } });
const page = (element: React.ReactNode) => <Suspense fallback={<Skeleton className="h-64" />}>{element}</Suspense>;

const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: "/", element: page(<Overview />) },
      { path: "/investigations", element: page(<Investigations />) },
      { path: "/investigations/:psiId", element: page(<InvestigationDetail />) },
      { path: "/ranking", element: page(<Ranking />) },
      { path: "/coverage", element: page(<Coverage />) },
      { path: "/assistant", element: page(<Assistant />) },
      { path: "/about", element: page(<About />) },
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
