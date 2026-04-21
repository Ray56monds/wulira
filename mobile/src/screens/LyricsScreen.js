import React, { useState, useEffect } from 'react';
import { View, Text, ScrollView, TextInput, TouchableOpacity, StyleSheet, Share, ActivityIndicator } from 'react-native';
import * as Clipboard from 'expo-clipboard';
import { getJob, searchLyrics, translateJob, exportLyrics } from '../api';

export default function LyricsScreen({ route }) {
  const jobId = route?.params?.jobId;
  const [job, setJob] = useState(null);
  const [search, setSearch] = useState('');
  const [results, setResults] = useState([]);
  const [translated, setTranslated] = useState(null);
  const [translating, setTranslating] = useState(false);
  const [targetLang, setTargetLang] = useState('en');

  useEffect(() => {
    if (jobId) loadJob();
  }, [jobId]);

  const loadJob = async () => {
    try {
      const data = await getJob(jobId);
      setJob(data);
      setTranslated(null);
    } catch {}
  };

  const handleSearch = async (q) => {
    setSearch(q);
    if (q.length < 2 || !jobId) { setResults([]); return; }
    try {
      const data = await searchLyrics(jobId, q);
      setResults(data.results || []);
    } catch {}
  };

  const handleTranslate = async () => {
    if (!jobId) return;
    setTranslating(true);
    try {
      const data = await translateJob(jobId, job?.language_code || 'lg', targetLang);
      setTranslated(data.translated || []);
    } catch {}
    setTranslating(false);
  };

  const handleShare = async () => {
    if (!jobId) return;
    try {
      const text = await exportLyrics(jobId, 'txt');
      await Share.share({ message: text, title: job?.title || 'Wulira Lyrics' });
    } catch {}
  };

  const handleCopy = async () => {
    if (!jobId) return;
    const text = await exportLyrics(jobId, 'txt');
    await Clipboard.setStringAsync(text);
  };

  if (!jobId) {
    return (
      <View style={s.container}><Text style={s.empty}>Select a job from the Jobs tab</Text></View>
    );
  }

  if (!job) {
    return (
      <View style={s.container}><ActivityIndicator color="#a29bfe" style={{ marginTop: 60 }} /></View>
    );
  }

  const segments = job.transcript || [];
  const highlightIds = new Set(results.map((r) => r.index));

  return (
    <ScrollView style={s.container}>
      {/* Header */}
      <Text style={s.title}>{job.title || 'Untitled'}</Text>
      <Text style={s.sub}>{job.uploader} · {job.language_detected} · {job.lyrics_source}</Text>

      {/* Actions */}
      <View style={s.actions}>
        <TouchableOpacity style={s.actionBtn} onPress={handleShare}>
          <Text style={s.actionText}>📤 Share</Text>
        </TouchableOpacity>
        <TouchableOpacity style={s.actionBtn} onPress={handleCopy}>
          <Text style={s.actionText}>📋 Copy</Text>
        </TouchableOpacity>
        <TouchableOpacity style={s.actionBtn} onPress={handleTranslate}>
          <Text style={s.actionText}>{translating ? '...' : '🌍 Translate'}</Text>
        </TouchableOpacity>
      </View>

      {/* Translate target */}
      <View style={s.row}>
        {['en', 'fr', 'sw', 'es', 'lg'].map((c) => (
          <TouchableOpacity key={c} style={[s.chip, targetLang === c && s.chipActive]} onPress={() => setTargetLang(c)}>
            <Text style={[s.chipLabel, targetLang === c && { color: '#fff' }]}>{c.toUpperCase()}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Search */}
      <TextInput style={s.searchInput} placeholder="Search lyrics..." placeholderTextColor="#666" value={search} onChangeText={handleSearch} />

      {/* Lyrics */}
      <View style={s.lyricsBox}>
        {segments.map((seg, i) => {
          const isHighlight = highlightIds.has(i);
          const trans = translated?.[i];
          return (
            <View key={i} style={[s.line, isHighlight && s.lineHighlight]}>
              {seg.start != null && <Text style={s.ts}>{fmtTime(seg.start)}</Text>}
              <View style={{ flex: 1 }}>
                <Text style={s.lineText}>{seg.text}</Text>
                {trans?.translated && <Text style={s.transText}>{trans.text}</Text>}
              </View>
            </View>
          );
        })}
      </View>
    </ScrollView>
  );
}

function fmtTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a0f', padding: 16 },
  empty: { color: '#888', textAlign: 'center', marginTop: 60 },
  title: { fontSize: 20, fontWeight: '700', color: '#e0e0e0', marginTop: 10 },
  sub: { color: '#888', fontSize: 13, marginTop: 4, marginBottom: 16 },
  actions: { flexDirection: 'row', gap: 10, marginBottom: 12 },
  actionBtn: { backgroundColor: '#1a1a26', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: '#2a2a3a' },
  actionText: { color: '#a29bfe', fontSize: 13 },
  row: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  chip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, backgroundColor: '#1a1a26', borderWidth: 1, borderColor: '#2a2a3a' },
  chipActive: { backgroundColor: '#6c5ce7', borderColor: '#6c5ce7' },
  chipLabel: { color: '#888', fontSize: 12, fontWeight: '600' },
  searchInput: { backgroundColor: '#1a1a26', borderWidth: 1, borderColor: '#2a2a3a', borderRadius: 8, padding: 10, color: '#e0e0e0', fontSize: 14, marginBottom: 12 },
  lyricsBox: { backgroundColor: '#12121a', borderRadius: 10, padding: 12 },
  line: { flexDirection: 'row', paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: '#1a1a26' },
  lineHighlight: { backgroundColor: 'rgba(253,203,110,0.1)' },
  ts: { color: '#6c5ce7', fontSize: 11, fontFamily: 'monospace', width: 44, marginTop: 2 },
  lineText: { color: '#e0e0e0', fontSize: 14, lineHeight: 22 },
  transText: { color: '#a29bfe', fontSize: 13, lineHeight: 20, marginTop: 2, fontStyle: 'italic' },
});
