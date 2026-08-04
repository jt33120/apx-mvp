import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";
import App from "./App";
import { ViewerRoute } from "./viewer";
import "./tokens.css";

// The console at "/", the pièce viewer at "/piece/:pieceId" (a focused route, Story 3.5d) — every
// data access remains an HTTP call to the one API, and the viewer applies the scope pre-filter
// server-side before any render (AD-13/14).
const router = createBrowserRouter([
  { path: "/", element: <App /> },
  { path: "/piece/:pieceId", element: <ViewerRoute /> },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
