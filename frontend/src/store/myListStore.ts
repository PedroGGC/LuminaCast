import { create } from 'zustand';
import { fetchMyList, addToMyList, removeFromMyList } from '../lib/api';

interface MyListStore {
  items: (number | string)[];
  loading: boolean;
  initialized: boolean;
  fetchList: () => Promise<void>;
  add: (id: number | string) => Promise<void>;
  remove: (id: number | string) => Promise<void>;
}

export const useMyListStore = create<MyListStore>((set, get) => ({
  items: [],
  loading: false,
  initialized: false,
  fetchList: async () => {
    if (get().initialized) return;
    set({ loading: true });
    try {
      const data = await fetchMyList();
      const newItems = data.flatMap(i => [i.media_id]);
      set({ items: newItems, initialized: true });
    } catch (e) {
      console.error('Failed to fetch my list:', e);
    } finally {
      set({ loading: false });
    }
  },
  add: async (id) => {
    try {
      const numericId = Number(String(id).replace('mal_', '').replace('tmdb_', ''));
      if (get().items.includes(numericId)) return;
      set({ items: [...get().items, numericId] });
      await addToMyList(numericId);
    } catch (e) {
      set({ items: get().items.filter(i => i !== id) });
      console.error(e);
    }
  },
  remove: async (id) => {
    try {
      const numericId = Number(String(id).replace('mal_', '').replace('tmdb_', ''));
      set({ items: get().items.filter(i => i !== numericId) });
      await removeFromMyList(numericId);
    } catch (e) {
      console.error(e);
    }
  }
}));
