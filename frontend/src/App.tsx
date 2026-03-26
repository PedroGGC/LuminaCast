import { Routes, Route, Navigate } from "react-router-dom";
import Navbar from "./components/Navbar";
import Home from "./pages/Home";
import AnimeDetail from "./pages/AnimeDetail";
import AuthPage from "./pages/AuthPage";
import ProtectedRoute from "./components/ProtectedRoute";
import MyList from "./pages/MyList";
import Search from "./pages/Search";
import VideoPlayer from "./pages/VideoPlayer";
import Profile from "./pages/Profile";
import CatalogPage from "./pages/CatalogPage";

function App() {
  return (
    <div className="min-h-screen bg-lunima-black">
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<AuthPage />} />
        <Route path="/register" element={<AuthPage />} />
        
        <Route element={<ProtectedRoute />}>
          <Route path="/home" element={<><Navbar /><Home /></>} />
          <Route path="/animes" element={<><Navbar /><CatalogPage type="anime" /></>} />
          <Route path="/desenhos" element={<><Navbar /><CatalogPage type="desenho" /></>} />
          <Route path="/minha-lista" element={<><Navbar /><MyList /></>} />
          <Route path="/search" element={<><Navbar /><Search /></>} />
          <Route path="/media/:id" element={<><Navbar /><AnimeDetail /></>} />
          <Route path="/watch/:id" element={<VideoPlayer />} />
          <Route path="/profile" element={<><Navbar /><Profile /></>} />
        </Route>
      </Routes>
    </div>
  );
}

export default App;
