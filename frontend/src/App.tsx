import { Route, Routes } from "react-router-dom";
import Layout from "@/components/Layout";
import HomePage from "@/pages/Home";
import ProjectView from "@/pages/ProjectView";
import EditorPage from "@/pages/Editor";
import PlaybackPage from "@/pages/Playback";
import LibraryPage from "@/pages/Library";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="project/:id" element={<ProjectView />} />
        <Route path="project/:id/editor" element={<EditorPage />} />
        <Route path="project/:id/play" element={<PlaybackPage />} />
        <Route path="library" element={<LibraryPage />} />
      </Route>
    </Routes>
  );
}
