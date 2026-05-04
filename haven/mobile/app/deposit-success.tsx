import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import Animated, {
  useSharedValue, useAnimatedStyle, withSpring, withDelay,
} from 'react-native-reanimated';
import { useEffect } from 'react';
import { Colors, Typography, Spacing, Radius } from '../constants/theme';

export default function DepositSuccess() {
  const scale = useSharedValue(0);
  const opacity = useSharedValue(0);

  useEffect(() => {
    scale.value = withSpring(1, { damping: 12 });
    opacity.value = withDelay(200, withSpring(1));
  }, []);

  const checkStyle = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
    opacity: opacity.value,
  }));

  return (
    <View style={styles.container}>
      <Animated.View style={[styles.check, checkStyle]}>
        <Text style={styles.checkIcon}>✓</Text>
      </Animated.View>

      <Text style={styles.title}>Deposit successful!</Text>
      <Text style={styles.subtitle}>
        Your money is now being put to work.{'\n'}
        You'll start earning yield within 24 hours.
      </Text>

      <View style={styles.apyBadge}>
        <Text style={styles.apyText}>6.8% APY · Sharia certified ✓</Text>
      </View>

      <TouchableOpacity
        style={styles.cta}
        onPress={() => router.replace('/home')}
        activeOpacity={0.85}
      >
        <LinearGradient
          colors={[Colors.accent, '#2da882']}
          style={styles.ctaGradient}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 0 }}
        >
          <Text style={styles.ctaText}>View my balance</Text>
        </LinearGradient>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing.xl,
  },
  check: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: Colors.accentDim,
    borderWidth: 2,
    borderColor: Colors.accent,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.xl,
  },
  checkIcon: { color: Colors.accent, fontSize: 36 },
  title: { ...Typography.h1, textAlign: 'center', marginBottom: Spacing.sm },
  subtitle: {
    ...Typography.body,
    color: Colors.textSecondary,
    textAlign: 'center',
    lineHeight: 26,
    marginBottom: Spacing.xl,
  },
  apyBadge: {
    backgroundColor: Colors.accentDim,
    borderWidth: 1,
    borderColor: Colors.accentBorder,
    borderRadius: Radius.full,
    paddingHorizontal: Spacing.lg,
    paddingVertical: 8,
    marginBottom: Spacing.xl,
  },
  apyText: { color: Colors.accent, fontFamily: 'Inter_600SemiBold', fontSize: 15 },
  cta: { width: '100%', borderRadius: Radius.lg, overflow: 'hidden' },
  ctaGradient: { paddingVertical: 18, alignItems: 'center' },
  ctaText: { fontSize: 17, fontFamily: 'Inter_600SemiBold', color: '#000' },
});
