import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView, Platform,
} from 'react-native';
import { router } from 'expo-router';
import { clearSession, loadSession } from '../store/auth';
import { useState, useEffect } from 'react';
import { Colors, Typography, Spacing, Radius } from '../constants/theme';

type Row = { label: string; icon: string; onPress: () => void; danger?: boolean };

export default function Settings() {
  const [user, setUser] = useState<{ email?: string; kyc_status?: string } | null>(null);

  useEffect(() => {
    loadSession().then(s => setUser(s?.user ?? null));
  }, []);

  async function handleLogout() {
    await clearSession();
    router.replace('/login');
  }

  const rows: Row[] = [
    { icon: '🪪', label: 'Sharia certification', onPress: () => {} },
    { icon: '❓', label: 'How Haven works', onPress: () => {} },
    { icon: '🔒', label: 'Change password', onPress: () => {} },
    { icon: '📄', label: 'Terms of Service', onPress: () => {} },
    { icon: '🔐', label: 'Privacy Policy', onPress: () => {} },
    { icon: '💬', label: 'Contact support', onPress: () => {} },
    { icon: '🚪', label: 'Log out', onPress: handleLogout, danger: true },
  ];

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <TouchableOpacity style={styles.back} onPress={() => router.back()}>
        <Text style={styles.backText}>← Back</Text>
      </TouchableOpacity>

      <Text style={styles.title}>Settings</Text>

      {/* Profile card */}
      <View style={styles.profileCard}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>{(user?.email?.[0] ?? '?').toUpperCase()}</Text>
        </View>
        <View>
          <Text style={styles.profileEmail}>{user?.email ?? ''}</Text>
          <View style={styles.kycBadge}>
            <Text style={styles.kycText}>
              {user?.kyc_status === 'approved' ? '✓ Verified' : '⚠ Unverified'}
            </Text>
          </View>
        </View>
      </View>

      {/* Settings rows */}
      <View style={styles.rowsContainer}>
        {rows.map((row, i) => (
          <TouchableOpacity
            key={i}
            style={[
              styles.row,
              i === 0 && styles.rowFirst,
              i === rows.length - 1 && styles.rowLast,
            ]}
            onPress={row.onPress}
            activeOpacity={0.7}
          >
            <Text style={styles.rowIcon}>{row.icon}</Text>
            <Text style={[styles.rowLabel, row.danger && styles.rowLabelDanger]}>
              {row.label}
            </Text>
            {!row.danger && <Text style={styles.chevron}>›</Text>}
          </TouchableOpacity>
        ))}
      </View>

      <Text style={styles.version}>Haven v1.0.0 · Devnet</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  content: {
    paddingHorizontal: Spacing.xl,
    paddingTop: Platform.OS === 'ios' ? 60 : 40,
    paddingBottom: 60,
  },
  back: { marginBottom: Spacing.xl },
  backText: { color: Colors.accent, fontSize: 16 },
  title: { ...Typography.h1, marginBottom: Spacing.xl },
  profileCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.lg,
    padding: Spacing.lg,
    marginBottom: Spacing.xl,
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: Colors.accentDim,
    borderWidth: 1,
    borderColor: Colors.accentBorder,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: { color: Colors.accent, fontSize: 20, fontFamily: 'Inter_700Bold' },
  profileEmail: { ...Typography.body, marginBottom: 4 },
  kycBadge: {
    backgroundColor: Colors.accentDim,
    borderRadius: Radius.full,
    paddingHorizontal: 8,
    paddingVertical: 2,
    alignSelf: 'flex-start',
  },
  kycText: { color: Colors.accent, fontSize: 12, fontFamily: 'Inter_600SemiBold' },
  rowsContainer: {
    backgroundColor: Colors.surface,
    borderRadius: Radius.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    overflow: 'hidden',
    marginBottom: Spacing.xl,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 18,
    paddingHorizontal: Spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
    gap: Spacing.md,
  },
  rowFirst: {},
  rowLast: { borderBottomWidth: 0 },
  rowIcon: { fontSize: 20, width: 28 },
  rowLabel: { flex: 1, ...Typography.body },
  rowLabelDanger: { color: Colors.negative },
  chevron: { color: Colors.textMuted, fontSize: 20, fontFamily: 'Inter_400Regular' },
  version: { ...Typography.micro, textAlign: 'center', color: Colors.textMuted },
});
