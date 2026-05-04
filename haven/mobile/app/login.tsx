import { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  KeyboardAvoidingView, Platform, ActivityIndicator,
} from 'react-native';
import { router } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { api } from '../store/api';
import { saveSession } from '../store/auth';
import { Colors, Typography, Spacing, Radius } from '../constants/theme';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleLogin() {
    if (!email || !password) { setError('Enter email and password'); return; }
    setLoading(true);
    setError('');
    try {
      const { token, user } = await api.login(email, password);
      await saveSession(token, user);
      if (user.kyc_status !== 'approved') {
        router.replace('/kyc');
      } else {
        router.replace('/home');
      }
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      style={styles.container}
    >
      <View style={styles.inner}>
        <Text style={styles.title}>Welcome back</Text>
        <Text style={styles.subtitle}>Log in to your Haven account.</Text>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <TextInput
          style={styles.input}
          placeholder="Email address"
          placeholderTextColor={Colors.textMuted}
          keyboardType="email-address"
          autoCapitalize="none"
          value={email}
          onChangeText={setEmail}
        />
        <TextInput
          style={styles.input}
          placeholder="Password"
          placeholderTextColor={Colors.textMuted}
          secureTextEntry
          value={password}
          onChangeText={setPassword}
        />

        <TouchableOpacity
          style={[styles.cta, loading && styles.ctaDisabled]}
          onPress={handleLogin}
          disabled={loading}
          activeOpacity={0.85}
        >
          {loading ? (
            <ActivityIndicator color="#000" />
          ) : (
            <LinearGradient
              colors={[Colors.accent, '#2da882']}
              style={styles.ctaGradient}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 0 }}
            >
              <Text style={styles.ctaText}>Log in</Text>
            </LinearGradient>
          )}
        </TouchableOpacity>

        <TouchableOpacity onPress={() => router.push('/signup')} style={styles.link}>
          <Text style={styles.linkText}>
            New to Haven? <Text style={{ color: Colors.accent }}>Create account</Text>
          </Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  inner: { flex: 1, paddingHorizontal: Spacing.xl, paddingTop: 80 },
  title: { ...Typography.h1, marginBottom: Spacing.sm },
  subtitle: { ...Typography.body, color: Colors.textSecondary, marginBottom: Spacing.xl },
  error: {
    fontSize: 14,
    color: Colors.negative,
    marginBottom: Spacing.md,
    backgroundColor: 'rgba(255,107,107,0.1)',
    padding: Spacing.sm,
    borderRadius: Radius.sm,
  },
  input: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    padding: Spacing.md,
    color: Colors.textPrimary,
    fontSize: 16,
    marginBottom: Spacing.md,
    fontFamily: 'Inter_400Regular',
  },
  cta: { borderRadius: Radius.lg, overflow: 'hidden', marginBottom: Spacing.lg },
  ctaDisabled: { opacity: 0.5 },
  ctaGradient: { paddingVertical: 18, alignItems: 'center' },
  ctaText: { fontSize: 17, fontFamily: 'Inter_600SemiBold', color: '#000' },
  link: { alignItems: 'center' },
  linkText: { ...Typography.small, color: Colors.textSecondary },
});
