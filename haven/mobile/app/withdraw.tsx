import { useState, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ActivityIndicator, Platform,
} from 'react-native';
import { router } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { api } from '../store/api';
import { Colors, Typography, Spacing, Radius } from '../constants/theme';

export default function Withdraw() {
  const [amount, setAmount] = useState('');
  const [balance, setBalance] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    api.getBalance().then(d => setBalance(parseFloat(d.balance_usd) || 0)).catch(() => {});
  }, []);

  const amountNum = parseFloat(amount) || 0;
  const isValid = amountNum > 0 && amountNum <= balance;

  async function handleWithdraw() {
    if (!isValid) { setError('Invalid withdrawal amount'); return; }
    setLoading(true);
    setError('');
    try {
      await api.requestWithdrawal(amountNum);
      setSuccess(true);
    } catch (err: any) {
      setError(err.message || 'Withdrawal failed');
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <View style={[styles.container, { justifyContent: 'center', alignItems: 'center' }]}>
        <Text style={{ fontSize: 56, marginBottom: Spacing.xl }}>✓</Text>
        <Text style={styles.title}>Withdrawal requested</Text>
        <Text style={[Typography.body, { color: Colors.textSecondary, textAlign: 'center', marginBottom: Spacing.xl }]}>
          ${amountNum.toFixed(2)} will arrive in 1–2 business days to your bank account.
        </Text>
        <TouchableOpacity style={styles.cta} onPress={() => router.replace('/home')}>
          <LinearGradient colors={[Colors.accent, '#2da882']} style={styles.ctaGradient} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}>
            <Text style={styles.ctaText}>Back to home</Text>
          </LinearGradient>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <TouchableOpacity style={styles.back} onPress={() => router.back()}>
        <Text style={styles.backText}>← Back</Text>
      </TouchableOpacity>

      <Text style={styles.title}>Withdraw</Text>
      <Text style={styles.available}>Available: ${balance.toFixed(2)}</Text>

      <View style={styles.amountContainer}>
        <Text style={styles.currencySymbol}>$</Text>
        <TextInput
          style={styles.amountInput}
          placeholder="0.00"
          placeholderTextColor={Colors.textMuted}
          keyboardType="decimal-pad"
          value={amount}
          onChangeText={v => { if (/^\d*\.?\d{0,2}$/.test(v)) setAmount(v); }}
          autoFocus
        />
      </View>

      <TouchableOpacity onPress={() => setAmount(balance.toFixed(2))} style={styles.maxBtn}>
        <Text style={styles.maxText}>Withdraw max</Text>
      </TouchableOpacity>

      <View style={styles.bankRow}>
        <Text style={styles.bankIcon}>🏦</Text>
        <View>
          <Text style={styles.bankName}>Connected bank account</Text>
          <Text style={styles.bankSub}>Arrives in 1–2 business days</Text>
        </View>
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <TouchableOpacity
        style={[styles.cta, (!isValid || loading) && styles.ctaDisabled]}
        onPress={handleWithdraw}
        disabled={!isValid || loading}
        activeOpacity={0.85}
      >
        {loading ? (
          <View style={[styles.ctaGradient, { backgroundColor: Colors.accentDim, flexDirection: 'row', gap: 8 }]}>
            <ActivityIndicator color="#000" size="small" />
            <Text style={[styles.ctaText, { color: '#000' }]}>Requesting...</Text>
          </View>
        ) : (
          <LinearGradient colors={[Colors.accent, '#2da882']} style={styles.ctaGradient} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}>
            <Text style={styles.ctaText}>
              {isValid ? `Withdraw $${amountNum.toFixed(2)}` : 'Withdraw'}
            </Text>
          </LinearGradient>
        )}
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
    paddingHorizontal: Spacing.xl,
    paddingTop: Platform.OS === 'ios' ? 60 : 40,
  },
  back: { marginBottom: Spacing.xl },
  backText: { color: Colors.accent, fontSize: 16 },
  title: { ...Typography.h1, marginBottom: Spacing.sm },
  available: { ...Typography.small, color: Colors.textSecondary, marginBottom: Spacing.xl },
  amountContainer: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', marginBottom: Spacing.sm },
  currencySymbol: { fontSize: 36, fontFamily: 'Inter_600SemiBold', color: Colors.textSecondary, marginRight: 4, marginTop: 8 },
  amountInput: { fontSize: 64, fontFamily: 'Inter_700Bold', color: Colors.textPrimary, minWidth: 120, textAlign: 'center' },
  maxBtn: { alignItems: 'center', marginBottom: Spacing.xl },
  maxText: { color: Colors.accent, fontSize: 14, fontFamily: 'Inter_600SemiBold' },
  bankRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    padding: Spacing.md,
    marginBottom: Spacing.xl,
  },
  bankIcon: { fontSize: 24 },
  bankName: { ...Typography.body },
  bankSub: { ...Typography.small, color: Colors.textSecondary },
  error: { color: Colors.negative, fontSize: 14, textAlign: 'center', marginBottom: Spacing.md },
  cta: { borderRadius: Radius.lg, overflow: 'hidden' },
  ctaDisabled: { opacity: 0.4 },
  ctaGradient: { paddingVertical: 18, alignItems: 'center' },
  ctaText: { fontSize: 17, fontFamily: 'Inter_600SemiBold', color: '#000' },
});
