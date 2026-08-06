import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";
import App from "./App";
import { TriageRoute } from "./triage";
import { ViewerRoute } from "./viewer";
import "./tokens.css";

// The console at "/", the pièce viewer at "/piece/:pieceId" (a focused route, Story 3.5d) and the
// triage surface at "/matter/:matter/triage" (Story 4.10) — every data access remains an HTTP call
// to the one API, and each route applies the scope pre-filter server-side before any render
// (AD-13/14).
const router = createBrowserRouter([
  { path: "/", element: <App /> },
  { path: "/piece/:pieceId", element: <ViewerRoute /> },
  { path: "/matter/:matter/triage", element: <TriageRoute /> },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
