import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";
import App from "./App";
import "./tokens.css";

// One empty route. The router is here so later stories add routes without
// restructuring, and so every data access remains an HTTP call to the one API.
const router = createBrowserRouter([{ path: "/", element: <App /> }]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
