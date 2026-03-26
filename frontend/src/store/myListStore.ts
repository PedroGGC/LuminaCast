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
      // Store both the internal DB ID and the prefixed external ID 
      // so `includes` works accurately on Home (prefixed strings) and Details (internal IDs).
      const newItems = data.flatMap(i => {
        if (!i.media) return [i.media_id];
        const prefix = i.media.media_type === 'anime' ? 'mal_' : 'tmdb_';
        return [i.media_id, `${prefix}${i.media.external_id}`];
      });
      set({ items: newItems, initialized: true });
    } catch (e) {
      console.error('Failed to fetch my list:', e);
    } finally {
      set({ loading: false });
    }
  },
  add: async (id) => {
    try {
      // Evita duplicatas no estado local otimista
      if (get().items.includes(id)) return;
      
      set({ items: [...get().items, id] });
      await addToMyList(id);
    } catch (e) {
      set({ items: get().items.filter(i => i !== id) });
      console.error(e);
    }
  },
  remove: async (id) => {
    try {
      set({ items: get().items.filter(i => i !== id) });
      await removeFromMyList(id);
    } catch (e) {
      console.error(e);
    }
  }
}));
