import { useState, useEffect, useRef, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  RefreshControl, Platform,
} from 'react-native';
import Animated, {
  useSharedValue, useAnimatedStyle, withTiming,
  Easing, withRepeat, withSequence,
} from 'react-native-reanimated';
import { router } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { api } from '../store/api';
import { loadSession } from '../store/auth';
import { Colors, Typography, Spacing, Radius } from '../constants/theme';

type Transaction = {
  id: string;
  type: 'deposit' | 'withdrawal' | 'yield';
  amount_usd: string;
  status: string;
  created_at: string;
};

// ──────────────────────────────────────────────
// Live yield ticker hook
// Calculates yield per second and animates the
// last two decimal places every 3 seconds.
// ──────────────────────────────────────────────
function useYieldTicker(balanceUsd: number, apy: number) {
  const [displayBalance, setDisplayBalance] = useState(balanceUsd);
  const accumulatedRef = useRef(0);
  const lastTickRef = useRef(Date.now());

  const yieldPerSecond = (balanceUsd * apy) / 365 / 24 / 3600;

  useEffect(() => {
    if (yieldPerSecond <= 0) return;

    const interval = setInterval(() => {
      const now = Date.now();
      const elapsed = (now - lastTickRef.current) / 1000;
      lastTickRef.current = now;
      accumulatedRef.current += yieldPerSecond * elapsed;

      setDisplayBalance(prev => {
        const newVal = balanceUsd + accumulatedRef.current;
        return newVal;
      });
    }, 3000);

    return () => clearInterval(interval);
  }, [balanceUsd, yieldPerSecond]);

  return displayBalance;
}

function formatBalance(amount: number): { whole: string; cents: string } {
  const fixed = amount.toFixed(2);
  const [whole, cents] = fixed.split('.');
  return {
    whole: parseInt(whole).toLocaleString('en-US'),
    cents: cents,
  };
}

function txIcon(type: string) {
  if (type === 'deposit')    return '↓';
  if (type === 'withdrawal') return '↑';
  if (type === 'yield')      return '✦';
  return '·';
}

function txLabel(type: string) {
  if (type === 'deposit')    return 'Deposit';
  if (type === 'withdrawal') return 'Withdrawal';
  if (type === 'yield')      return 'Yield earned';
  return type;
}

function txColor(type: string) {
  if (type === 'deposit')    return Colors.textPrimary;
  if (type === 'withdrawal') return Colors.negative;
  if (type === 'yield')      return Colors.accent;
  return Colors.textSecondary;
}

export default function HomeScreen() {
  const [user, setUser] = useState<{ first_name?: string } | null>(null);
  const [balanceUsd, setBalanceUsd] = useState(0);
  const [apy, setApy] = useState(0.068);
  const [todayYield, setTodayYield] = useState(0);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);

  // Animated cents glow
  const glowOpacity = useSharedValue(1);
  const glowStyle = useAnimatedStyle(() => ({ opacity: glowOpacity.value }));

  const liveBalance = useYieldTicker(balanceUsd, apy);
  const { whole, cents } = formatBalance(liveBalance);

  // Pulse animation on every tick
  useEffect(() => {
    const timer = setInterval(() => {
      glowOpacity.value = withSequence(
        withTiming(0.4, { duration: 300, easing: Easing.out(Easing.quad) }),
        withTiming(1,   { duration: 600, easing: Easing.in(Easing.quad) })
      );
    }, 3000);
    return () => clearInterval(timer);
  }, []);

  async function load() {
    try {
      const session = await loadSession();
      if (!session) { router.replace('/login'); return; }
      setUser(session.user);

      const [balData, txData, apyData] = await Promise.all([
        api.getBalance(),
        api.getTransactions(),
        api.getCurrentApy(),
      ]);

      const bal = parseFloat(balData.balance_usd) || 0;
      const apyVal = parseFloat(balData.apy) || 0.068;
      setBalanceUsd(bal);
      setApy(apyVal);
      setTodayYield((bal * apyVal) / 365);
      setTransactions(txData.transactions || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, []);

  const greetingHour = new Date().getHours();
  const greeting =
    greetingHour < 12 ? 'Good morning' :
    greetingHour < 17 ? 'Good afternoon' : 'Good evening';

  const firstName = user?.first_name || '';

  return (
    <View style={styles.container}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.accent} />
        }
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.greeting}>
            {greeting}{firstName ? `, ${firstName}` : ''} 👋
          </Text>
          <TouchableOpacity onPress={() => router.push('/settings')}>
            <View style={styles.avatarCircle}>
              <Text style={styles.avatarText}>{(firstName || '?')[0].toUpperCase()}</Text>
            </View>
          </TouchableOpacity>
        </View>

        {/* Balance card */}
        <View style={styles.cardWrapper}>
          <LinearGradient
            colors={['rgba(61,191,152,0.08)', 'rgba(61,191,152,0.03)']}
            style={styles.card}
          >
            <View style={styles.cardInner}>
              <Text style={styles.balanceLabel}>Total balance</Text>

              <View style={styles.balanceRow}>
                <Text style={styles.balanceDollar}>$</Text>
                <Text style={styles.balanceWhole}>{whole}</Text>
                <Text style={styles.balanceDot}>.</Text>
                <Animated.Text style={[styles.balanceCents, glowStyle]}>
                  {cents}
                </Animated.Text>
              </View>

              {todayYield > 0 && (
                <View style={styles.yieldPill}>
                  <Text style={styles.yieldPillText}>
                    +${todayYield.toFixed(2)} earned today
                  </Text>
                </View>
              )}

              <View style={styles.apyRow}>
                <Text style={styles.apyText}>{(apy * 100).toFixed(1)}% APY</Text>
                <View style={styles.shariaDot} />
                <Text style={styles.shariaText}>Sharia certified ✓</Text>
              </View>
            </View>
          </LinearGradient>
        </View>

        {/* Action buttons */}
        <View style={styles.actions}>
          <TouchableOpacity
            style={styles.actionBtn}
            onPress={() => router.push('/add-money')}
            activeOpacity={0.85}
          >
            <LinearGradient
              colors={[Colors.accent, '#2da882']}
              style={styles.actionBtnGradient}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 0 }}
            >
              <Text style={styles.actionBtnText}>+ Add money</Text>
            </LinearGradient>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.actionBtn, styles.actionBtnSecondary]}
            onPress={() => router.push('/withdraw')}
            activeOpacity={0.85}
          >
            <Text style={styles.actionBtnSecondaryText}>↑ Withdraw</Text>
          </TouchableOpacity>
        </View>

        {/* How it works */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>How your money works</Text>
          <View style={styles.flowSteps}>
            {[
              { icon: '💳', label: 'You deposit' },
              { icon: '⛓️', label: 'Staked on Solana' },
              { icon: '💰', label: 'Earns tx fees' },
              { icon: '✦', label: 'You get paid daily' },
            ].map((step, i) => (
              <View key={i} style={styles.flowStep}>
                <Text style={styles.flowIcon}>{step.icon}</Text>
                <Text style={styles.flowLabel}>{step.label}</Text>
                {i < 3 && <Text style={styles.flowArrow}>→</Text>}
              </View>
            ))}
          </View>
        </View>

        {/* Recent transactions */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Recent activity</Text>
          {transactions.length === 0 ? (
            <Text style={styles.emptyText}>No transactions yet. Make your first deposit!</Text>
          ) : (
            transactions.slice(0, 10).map(tx => (
              <View key={tx.id} style={styles.txRow}>
                <View style={[styles.txIcon, { borderColor: txColor(tx.type) + '44' }]}>
                  <Text style={[styles.txIconText, { color: txColor(tx.type) }]}>
                    {txIcon(tx.type)}
                  </Text>
                </View>
                <View style={styles.txInfo}>
                  <Text style={styles.txLabel}>{txLabel(tx.type)}</Text>
                  <Text style={styles.txDate}>
                    {new Date(tx.created_at).toLocaleDateString('en-US', {
                      month: 'short', day: 'numeric',
                    })}
                  </Text>
                </View>
                <View style={styles.txAmountCol}>
                  <Text style={[styles.txAmount, { color: txColor(tx.type) }]}>
                    {tx.type === 'withdrawal' ? '-' : '+'}${parseFloat(tx.amount_usd).toFixed(2)}
                  </Text>
                  <Text style={styles.txStatus}>{tx.status}</Text>
                </View>
              </View>
            ))
          )}

          {transactions.length > 10 && (
            <TouchableOpacity onPress={() => router.push('/transactions')}>
              <Text style={styles.viewAll}>View all transactions →</Text>
            </TouchableOpacity>
          )}
        </View>

        <View style={{ height: 40 }} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.xl,
    paddingTop: Platform.OS === 'ios' ? 60 : 40,
    paddingBottom: Spacing.md,
  },
  greeting: { ...Typography.h3 },
  avatarCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: Colors.accentDim,
    borderWidth: 1,
    borderColor: Colors.accentBorder,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: { color: Colors.accent, fontFamily: 'Inter_600SemiBold', fontSize: 15 },

  // Balance card
  cardWrapper: {
    marginHorizontal: Spacing.xl,
    marginVertical: Spacing.md,
    borderRadius: Radius.xl,
    borderWidth: 1,
    borderColor: Colors.accentBorder,
    overflow: 'hidden',
  },
  card: { borderRadius: Radius.xl },
  cardInner: { padding: Spacing.xl },
  balanceLabel: { ...Typography.small, color: Colors.textSecondary, marginBottom: Spacing.sm },
  balanceRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    marginBottom: Spacing.md,
  },
  balanceDollar: {
    fontSize: 28,
    fontFamily: 'Inter_600SemiBold',
    color: Colors.textPrimary,
    marginBottom: 4,
    marginRight: 2,
  },
  balanceWhole: {
    fontSize: 52,
    fontFamily: 'Inter_700Bold',
    color: Colors.textPrimary,
    lineHeight: 56,
  },
  balanceDot: {
    fontSize: 52,
    fontFamily: 'Inter_700Bold',
    color: Colors.textPrimary,
    lineHeight: 56,
  },
  balanceCents: {
    fontSize: 32,
    fontFamily: 'Inter_600SemiBold',
    color: Colors.accent,
    marginBottom: 4,
  },
  yieldPill: {
    backgroundColor: Colors.accentDim,
    borderWidth: 1,
    borderColor: Colors.accentBorder,
    borderRadius: Radius.full,
    paddingHorizontal: Spacing.md,
    paddingVertical: 4,
    alignSelf: 'flex-start',
    marginBottom: Spacing.md,
  },
  yieldPillText: { color: Colors.accent, fontSize: 13, fontFamily: 'Inter_600SemiBold' },
  apyRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  apyText: { ...Typography.small, color: Colors.textSecondary },
  shariaDot: { width: 3, height: 3, borderRadius: 2, backgroundColor: Colors.textMuted },
  shariaText: { ...Typography.small, color: Colors.textSecondary },

  // Actions
  actions: {
    flexDirection: 'row',
    paddingHorizontal: Spacing.xl,
    gap: Spacing.md,
    marginBottom: Spacing.xl,
  },
  actionBtn: { flex: 1, borderRadius: Radius.lg, overflow: 'hidden' },
  actionBtnGradient: { paddingVertical: 16, alignItems: 'center' },
  actionBtnText: { fontSize: 16, fontFamily: 'Inter_600SemiBold', color: '#000' },
  actionBtnSecondary: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingVertical: 16,
    alignItems: 'center',
  },
  actionBtnSecondaryText: { fontSize: 16, fontFamily: 'Inter_600SemiBold', color: Colors.textPrimary },

  // How it works flow
  section: { paddingHorizontal: Spacing.xl, marginBottom: Spacing.xl },
  sectionTitle: { ...Typography.h3, marginBottom: Spacing.md },
  flowSteps: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 2,
  },
  flowStep: { alignItems: 'center', position: 'relative' },
  flowIcon: { fontSize: 24, marginBottom: 4 },
  flowLabel: { ...Typography.micro, color: Colors.textSecondary, textAlign: 'center', maxWidth: 60 },
  flowArrow: { color: Colors.textMuted, fontSize: 18, marginHorizontal: 4, marginBottom: 12 },

  // Transactions
  emptyText: { ...Typography.body, color: Colors.textMuted, textAlign: 'center', paddingVertical: Spacing.xl },
  txRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
    gap: Spacing.md,
  },
  txIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  txIconText: { fontSize: 16, fontFamily: 'Inter_600SemiBold' },
  txInfo: { flex: 1 },
  txLabel: { ...Typography.body, marginBottom: 2 },
  txDate: { ...Typography.micro },
  txAmountCol: { alignItems: 'flex-end' },
  txAmount: { ...Typography.body, fontFamily: 'Inter_600SemiBold' },
  txStatus: { ...Typography.micro, textTransform: 'capitalize' },
  viewAll: { color: Colors.accent, fontSize: 14, textAlign: 'center', marginTop: Spacing.md },
});
