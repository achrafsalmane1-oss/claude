import { useState } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ActivityIndicator,
} from 'react-native';
import { router } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { api } from '../store/api';
import { Colors, Typography, Spacing, Radius } from '../constants/theme';

export default function KYCScreen() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleVerify() {
    setLoading(true);
    setError('');
    try {
      const { session_token, inquiry_id } = await api.initiateKyc();

      // In production: open Persona's native SDK with session_token
      // import Persona from 'react-native-persona';
      // await Persona.start({ sessionToken: session_token, ... });
      //
      // For now (MOCK_MODE): skip directly to home
      console.log('KYC initiated:', { session_token, inquiry_id });

      // Simulate approval in mock mode
      await new Promise(r => setTimeout(r, 1500));
      router.replace('/home');
    } catch (err: any) {
      setError(err.message || 'KYC initiation failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={styles.container}>
      <View style={styles.inner}>
        <View style={styles.iconContainer}>
          <Text style={styles.icon}>🪪</Text>
        </View>

        <Text style={styles.title}>Quick identity check</Text>
        <Text style={styles.subtitle}>
          Required by law to protect you and your money.
          Takes under 2 minutes.
        </Text>

        <View style={styles.steps}>
          {['Take a photo of your ID', 'Take a quick selfie', "You're verified"].map((step, i) => (
            <View key={i} style={styles.step}>
              <View style={styles.stepNumber}>
                <Text style={styles.stepNumberText}>{i + 1}</Text>
              </View>
              <Text style={styles.stepLabel}>{step}</Text>
            </View>
          ))}
        </View>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <TouchableOpacity
          style={[styles.cta, loading && styles.ctaDisabled]}
          onPress={handleVerify}
          disabled={loading}
          activeOpacity={0.85}
        >
          {loading ? (
            <View style={styles.ctaLoading}>
              <ActivityIndicator color="#000" />
              <Text style={[styles.ctaText, { marginLeft: 10 }]}>Starting verification...</Text>
            </View>
          ) : (
            <LinearGradient
              colors={[Colors.accent, '#2da882']}
              style={styles.ctaGradient}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 0 }}
            >
              <Text style={styles.ctaText}>Verify now</Text>
            </LinearGradient>
          )}
        </TouchableOpacity>

        <TouchableOpacity onPress={() => router.replace('/home')} style={styles.skip}>
          <Text style={styles.skipText}>I'll do this later</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  inner: {
    flex: 1,
    paddingHorizontal: Spacing.xl,
    paddingTop: 80,
  },
  iconContainer: { marginBottom: Spacing.xl },
  icon: { fontSize: 56 },
  title: { ...Typography.h1, marginBottom: Spacing.sm },
  subtitle: {
    ...Typography.body,
    color: Colors.textSecondary,
    lineHeight: 26,
    marginBottom: Spacing.xl,
  },
  steps: { marginBottom: Spacing.xl },
  step: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    marginBottom: Spacing.md,
  },
  stepNumber: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: Colors.accentDim,
    borderWidth: 1,
    borderColor: Colors.accentBorder,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepNumberText: { color: Colors.accent, fontFamily: 'Inter_600SemiBold', fontSize: 14 },
  stepLabel: { ...Typography.body, color: Colors.textSecondary },
  error: {
    color: Colors.negative,
    fontSize: 14,
    marginBottom: Spacing.md,
    backgroundColor: 'rgba(255,107,107,0.1)',
    padding: Spacing.sm,
    borderRadius: Radius.sm,
  },
  cta: { borderRadius: Radius.lg, overflow: 'hidden', marginBottom: Spacing.md },
  ctaDisabled: { opacity: 0.7 },
  ctaGradient: { paddingVertical: 18, alignItems: 'center' },
  ctaLoading: {
    paddingVertical: 18,
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'center',
    backgroundColor: Colors.accentDim,
  },
  ctaText: { fontSize: 17, fontFamily: 'Inter_600SemiBold', color: '#000' },
  skip: { alignItems: 'center', paddingVertical: Spacing.sm },
  skipText: { ...Typography.small, color: Colors.textMuted },
});
