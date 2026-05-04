import { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ActivityIndicator, Platform, Alert,
} from 'react-native';
import { router } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { useStripe } from '@stripe/stripe-react-native';
import { api } from '../store/api';
import { Colors, Typography, Spacing, Radius } from '../constants/theme';

type PaymentMethod = 'apple_pay' | 'google_pay' | 'card';

export default function AddMoney() {
  const { initPaymentSheet, presentPaymentSheet } = useStripe();
  const [amount, setAmount] = useState('');
  const [method, setMethod] = useState<PaymentMethod>('apple_pay');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const amountNum = parseFloat(amount) || 0;
  const isValidAmount = amountNum >= 10;

  async function handleDeposit() {
    if (!isValidAmount) { setError('Minimum deposit is $10'); return; }
    setLoading(true);
    setError('');

    try {
      const { clientSecret } = await api.createDepositIntent(amountNum);

      // Initialize Stripe PaymentSheet (handles Apple Pay + Google Pay + card)
      const { error: initError } = await initPaymentSheet({
        paymentIntentClientSecret: clientSecret,
        merchantDisplayName: 'Haven Savings',
        applePay: {
          merchantCountryCode: 'US',
        },
        googlePay: {
          merchantCountryCode: 'US',
          testEnv: true,
        },
        defaultBillingDetails: {},
        appearance: {
          colors: {
            primary: Colors.accent,
            background: Colors.surface,
            componentBackground: Colors.surfaceElevated,
            componentText: Colors.textPrimary,
            placeholderText: Colors.textMuted,
          },
        },
      });

      if (initError) {
        setError(initError.message);
        return;
      }

      const { error: presentError } = await presentPaymentSheet();
      if (presentError) {
        if (presentError.code !== 'Canceled') {
          setError(presentError.message);
        }
        return;
      }

      // Success
      router.replace('/deposit-success');
    } catch (err: any) {
      setError(err.message || 'Deposit failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={styles.container}>
      {/* Nav */}
      <TouchableOpacity style={styles.back} onPress={() => router.back()}>
        <Text style={styles.backText}>← Back</Text>
      </TouchableOpacity>

      <Text style={styles.title}>Add money</Text>

      {/* Amount input */}
      <View style={styles.amountContainer}>
        <Text style={styles.currencySymbol}>$</Text>
        <TextInput
          style={styles.amountInput}
          placeholder="0.00"
          placeholderTextColor={Colors.textMuted}
          keyboardType="decimal-pad"
          value={amount}
          onChangeText={v => {
            // Only allow valid decimal format
            if (/^\d*\.?\d{0,2}$/.test(v)) setAmount(v);
          }}
          autoFocus
        />
      </View>

      <Text style={styles.minNote}>Minimum $10</Text>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      {/* Payment methods */}
      <Text style={styles.methodLabel}>Pay with</Text>
      <View style={styles.methods}>
        {([
          { id: 'apple_pay', label: Platform.OS === 'ios' ? '🍎  Apple Pay' : '🤖  Google Pay', show: true },
          { id: 'google_pay', label: '🏦  Bank transfer', show: true },
        ] as { id: PaymentMethod; label: string; show: boolean }[])
          .filter(m => m.show)
          .map(m => (
          <TouchableOpacity
            key={m.id}
            style={[styles.methodBtn, method === m.id && styles.methodBtnActive]}
            onPress={() => setMethod(m.id)}
            activeOpacity={0.7}
          >
            <Text style={[styles.methodText, method === m.id && styles.methodTextActive]}>
              {m.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <TouchableOpacity
        style={[styles.cta, (!isValidAmount || loading) && styles.ctaDisabled]}
        onPress={handleDeposit}
        disabled={!isValidAmount || loading}
        activeOpacity={0.85}
      >
        {loading ? (
          <View style={styles.ctaLoading}>
            <ActivityIndicator color="#000" size="small" />
            <Text style={[styles.ctaText, { marginLeft: 8, color: '#000' }]}>Processing...</Text>
          </View>
        ) : (
          <LinearGradient
            colors={[Colors.accent, '#2da882']}
            style={styles.ctaGradient}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 0 }}
          >
            <Text style={styles.ctaText}>
              {isValidAmount ? `Add $${amountNum.toFixed(2)}` : 'Add money'}
            </Text>
          </LinearGradient>
        )}
      </TouchableOpacity>

      <Text style={styles.footnote}>
        No fees · Funds typically available within 1–2 business days
      </Text>
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
  backText: { color: Colors.accent, fontSize: 16, fontFamily: 'Inter_400Regular' },
  title: { ...Typography.h1, marginBottom: Spacing.xl },
  amountContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.sm,
  },
  currencySymbol: {
    fontSize: 36,
    fontFamily: 'Inter_600SemiBold',
    color: Colors.textSecondary,
    marginRight: 4,
    marginTop: 8,
  },
  amountInput: {
    fontSize: 64,
    fontFamily: 'Inter_700Bold',
    color: Colors.textPrimary,
    minWidth: 120,
    textAlign: 'center',
  },
  minNote: { ...Typography.small, color: Colors.textMuted, textAlign: 'center', marginBottom: Spacing.xl },
  error: {
    color: Colors.negative,
    fontSize: 14,
    textAlign: 'center',
    marginBottom: Spacing.md,
  },
  methodLabel: { ...Typography.small, color: Colors.textSecondary, marginBottom: Spacing.sm },
  methods: { gap: Spacing.sm, marginBottom: Spacing.xl },
  methodBtn: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    paddingVertical: 16,
    paddingHorizontal: Spacing.md,
  },
  methodBtnActive: {
    borderColor: Colors.accent,
    backgroundColor: Colors.accentDim,
  },
  methodText: { ...Typography.body, color: Colors.textSecondary },
  methodTextActive: { color: Colors.accent },
  cta: { borderRadius: Radius.lg, overflow: 'hidden', marginBottom: Spacing.md },
  ctaDisabled: { opacity: 0.4 },
  ctaGradient: { paddingVertical: 18, alignItems: 'center' },
  ctaLoading: {
    backgroundColor: Colors.accentDim,
    paddingVertical: 18,
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
  },
  ctaText: { fontSize: 17, fontFamily: 'Inter_600SemiBold', color: '#000' },
  footnote: {
    ...Typography.micro,
    textAlign: 'center',
    color: Colors.textMuted,
  },
});
