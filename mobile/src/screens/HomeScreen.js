import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ActivityIndicator, ScrollView } from 'react-native';
import { submitJob, connectWebSocket } from '../api';

const MODELS = ['tiny', 'base', 'small', 'medium', 'large'];
const LANGUAGES = [
  { code: '', label: 'Auto-detect' },
  { code: 'lg', label: 'Luganda' },
  { code: 'sw', label: 'Kiswahili' },
  { code: 'en', label: 'English' },
  { code: 'fr', label: 'French' },
  { code: 'yo', label: 'Yoruba' },
  { code: 'ha', label: 'Hausa' },
  { code: 'am', label: 'Amharic' },
];

export default function HomeScreen({ navigation }) {
  const [url, setUrl] = useState('');
  const [model, setModel] = useState('base');
  const [lang, setLang] = useState('');
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState('');
  const [progress, setProgress] = useState(0);

  const handleSubmit = async () => {
    if (!url.trim()) return;
    setLoading(true);
    setStage('Submitting...');
    setProgress(0);
    try {
      const data = await submitJob(url.trim(), model, lang || null);
      if (data.job_id) {
        const ws = connectWebSocket(data.job_id, (msg) => {
          const stages = {
            queued: 'Queued...', downloading: 'Downloading audio...',
            detecting_language: 'Detecting language...', transcribing: 'Extracting lyrics...',
            done: '✓ Done!',
          };
          setStage(stages[msg.stage] || msg.stage);
          setProgress(msg.progress || 0);
          if (msg.stage === 'done') {
            ws.close();
            setLoading(false);
            navigation.navigate('Lyrics', { jobId: data.job_id });
          }
        });
      }
    } catch (e) {
      setStage('Error: ' + e.message);
      setLoading(false);
    }
  };

  return (
    <ScrollView style={s.container}>
      <Text style={s.title}>🎵 Wulira</Text>
      <Text style={s.subtitle}>Hear every word, in every language</Text>

      <TextInput
        style={s.input}
        placeholder="Paste YouTube URL..."
        placeholderTextColor="#666"
        value={url}
        onChangeText={setUrl}
        autoCapitalize="none"
      />

      <Text style={s.label}>Model</Text>
      <View style={s.row}>
        {MODELS.map((m) => (
          <TouchableOpacity key={m} style={[s.chip, model === m && s.chipActive]} onPress={() => setModel(m)}>
            <Text style={[s.chipText, model === m && s.chipTextActive]}>{m}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <Text style={s.label}>Language</Text>
      <View style={s.row}>
        {LANGUAGES.map((l) => (
          <TouchableOpacity key={l.code} style={[s.chip, lang === l.code && s.chipActive]} onPress={() => setLang(l.code)}>
            <Text style={[s.chipText, lang === l.code && s.chipTextActive]}>{l.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <TouchableOpacity style={s.btn} onPress={handleSubmit} disabled={loading}>
        {loading ? <ActivityIndicator color="#fff" /> : <Text style={s.btnText}>Extract Lyrics</Text>}
      </TouchableOpacity>

      {stage ? (
        <View style={s.progressBox}>
          <View style={[s.progressBar, { width: `${progress}%` }]} />
          <Text style={s.stageText}>{stage}</Text>
        </View>
      ) : null}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a0f', padding: 20 },
  title: { fontSize: 28, fontWeight: '700', color: '#a29bfe', textAlign: 'center', marginTop: 20 },
  subtitle: { color: '#888', textAlign: 'center', marginBottom: 30, fontSize: 14 },
  input: { backgroundColor: '#1a1a26', borderWidth: 1, borderColor: '#2a2a3a', borderRadius: 10, padding: 14, color: '#e0e0e0', fontSize: 16, marginBottom: 20 },
  label: { color: '#888', fontSize: 13, marginBottom: 8, marginTop: 4 },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 16 },
  chip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, backgroundColor: '#1a1a26', borderWidth: 1, borderColor: '#2a2a3a' },
  chipActive: { backgroundColor: '#6c5ce7', borderColor: '#6c5ce7' },
  chipText: { color: '#888', fontSize: 13 },
  chipTextActive: { color: '#fff' },
  btn: { backgroundColor: '#6c5ce7', padding: 16, borderRadius: 10, alignItems: 'center', marginTop: 10 },
  btnText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  progressBox: { marginTop: 20, backgroundColor: '#1a1a26', borderRadius: 10, padding: 16 },
  progressBar: { height: 4, backgroundColor: '#6c5ce7', borderRadius: 2, marginBottom: 10 },
  stageText: { color: '#888', fontSize: 13, textAlign: 'center' },
});
