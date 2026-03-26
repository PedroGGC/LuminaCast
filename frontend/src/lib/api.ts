export interface Episode {
  id: number;
  number: number;
  title: string | null;
  thumbnail: string | null;
  stream_url: string | null;
}

export interface MediaEpisode {
  id: number;
  media_id: number;
  season_number: number;
  episode_number: number;
  title: string | null;
  thumbnail_url: string | null;
}

export interface Anime {
  id: number | string;
  external_id?: string | null;
  title: string;
  synopsis: string | null;
  poster_url?: string | null;
  media_type?: string | null;
  cover_image?: string | null;
  banner_image?: string | null;
  rating?: number;
  year?: number | null;
  content_type?: string;
}

export interface AnimeDetail extends Anime {
  episodes: Episode[];
}

export interface Category {
  id: number;
  name: string;
  slug: string;
  animes: Anime[];
}

import axios, { InternalAxiosRequestConfig, AxiosResponse, AxiosError } from 'axios';
import { useAuthStore } from '../store/authStore';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
});

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = useAuthStore.getState().token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: any) => {
    return Promise.reject(error);
  }
);

api.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout();
    }
    return Promise.reject(error);
  }
);

export interface UserListResponse {
  id: number;
  user_id: number;
  media_id: number;
  media: Anime;
}

export async function fetchCatalog(contentType?: 'anime' | 'cartoon'): Promise<Category[]> {
  const url = contentType ? `/api/catalog?content_type=${contentType}` : "/api/catalog";
  const res = await api.get<Category[]>(url);
  return res.data;
}

export async function fetchAnimes(): Promise<Anime[]> {
  const res = await api.get<Anime[]>("/api/media/animes");
  return res.data;
}

export async function fetchDesenhos(): Promise<Anime[]> {
  const res = await api.get<Anime[]>("/api/media/desenhos");
  return res.data;
}

export async function fetchMyList(): Promise<UserListResponse[]> {
  const res = await api.get<UserListResponse[]>("/api/my-list");
  return res.data;
}

export const addToMyList = async (mediaId: number | string): Promise<UserListResponse> => {
  const response = await api.post<UserListResponse>("/api/my-list", { media_id: mediaId });
  return response.data;
};

export async function removeFromMyList(mediaId: number | string): Promise<void> {
  await api.delete(`/api/my-list/${mediaId}`);
}

export async function searchAnimes(query: string): Promise<Anime[]> {
  const res = await api.get<Anime[]>(`/api/search?q=${encodeURIComponent(query)}`);
  return res.data;
}

export async function fetchEpisode(id: number): Promise<Episode> {
  const res = await api.get<Episode>(`/api/episode/${id}`);
  return res.data;
}
