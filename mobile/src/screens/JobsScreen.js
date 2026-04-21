import React, { useState, useCallback } from 'react';
import { View, Text, FlatList, TouchableOpacity, StyleSheet, RefreshControl } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { getJobs, deleteJob } from '../api';

const BADGE_COLORS = { queued: '#fdcb6e', processing: '#74b9ff', done: '#00b894', error: '#e17055' };

export default function JobsScreen({ navigation }) {
  const [jobs, setJobs] = useState([]);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    try {
      const data = await getJobs(30);
      setJobs(data.jobs || []);
    } catch {}
  };

  useFocusEffect(useCallback(() => { load(); }, []));

  const onRefresh = async () => { setRefreshing(true); await load(); setRefreshing(false); };

  const handleDelete = async (id) => {
    await deleteJob(id);
    load();
  };

  const renderItem = ({ item }) => (
    <TouchableOpacity style={s.item} onPress={() => navigation.navigate('Lyrics', { jobId: item.job_id })}>
      <View style={s.itemLeft}>
        <View style={[s.badge, { backgroundColor: BADGE_COLORS[item.status] + '22' }]}>
          <Text style={[s.badgeText, { color: BADGE_COLORS[item.status] }]}>{item.status}</Text>
        </View>
        <View style={s.meta}>
          <Text style={s.itemTitle} numberOfLines={1}>{item.title || item.job_id?.slice(0, 12)}</Text>
          <Text style={s.itemSub}>{item.language_detected || ''} · {item.lyrics_source || ''}</Text>
        </View>
      </View>
      <TouchableOpacity onPress={() => handleDelete(item.job_id)} style={s.delBtn}>
        <Text style={s.delText}>✕</Text>
      </TouchableOpacity>
    </TouchableOpacity>
  );

  return (
    <View style={s.container}>
      <FlatList
        data={jobs}
        keyExtractor={(item) => item.job_id}
        renderItem={renderItem}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#a29bfe" />}
        ListEmptyComponent={<Text style={s.empty}>No jobs yet. Extract some lyrics!</Text>}
      />
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a0f' },
  item: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, borderBottomWidth: 1, borderBottomColor: '#2a2a3a' },
  itemLeft: { flexDirection: 'row', alignItems: 'center', flex: 1 },
  badge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  badgeText: { fontSize: 11, fontWeight: '700' },
  meta: { marginLeft: 12, flex: 1 },
  itemTitle: { color: '#e0e0e0', fontSize: 14, fontWeight: '600' },
  itemSub: { color: '#888', fontSize: 12, marginTop: 2 },
  delBtn: { padding: 8 },
  delText: { color: '#e17055', fontSize: 16 },
  empty: { color: '#888', textAlign: 'center', marginTop: 60, fontSize: 14 },
});
