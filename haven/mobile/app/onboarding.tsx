import { useState, useRef } from 'react';
import {
  View, Text, StyleSheet, Dimensions, TouchableOpacity,
  FlatList, Animated,
} from 'react-native';
import { router } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { Colors, Typography, Spacing, Radius } from '../constants/theme';

const { width } = Dimensions.get('window');

const SLIDES = [
  {
    id: '1',
    headline: 'Your bank pays 2%.',
    headline2: 'Haven pays up to 7%.',
    body: 'Earn real yield on your savings — powered by Solana staking.',
    icon: '📈',
  },
  {
    id: '2',
    headline: 'No riba.',
    headline2: 'No compromise.',
    body: 'Sharia-certified. Your money never touches interest-bearing products.',
    icon: '☪️',
  },
  {
    id: '3',
    headline: 'Deposit in seconds.',
    headline2: 'Withdraw anytime.',
    body: 'Apple Pay, Google Pay, or bank transfer. Your balance, your control.',
    icon: '⚡',
  },
];

export default function Onboarding() {
  const [currentIndex, setCurrentIndex] = useState(0);
  const flatListRef = useRef<FlatList>(null);

  function next() {
    if (currentIndex < SLIDES.length - 1) {
      flatListRef.current?.scrollToIndex({ index: currentIndex + 1 });
      setCurrentIndex(i => i + 1);
    } else {
      router.push('/signup');
    }
  }

  return (
    <LinearGradient colors={['#080808', '#0d1a15', '#080808']} style={styles.container}>
      <FlatList
        ref={flatListRef}
        data={SLIDES}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        keyExtractor={item => item.id}
        onMomentumScrollEnd={e => {
          setCurrentIndex(Math.round(e.nativeEvent.contentOffset.x / width));
        }}
        renderItem={({ item }) => (
          <View style={styles.slide}>
            <Text style={styles.icon}>{item.icon}</Text>
            <Text style={styles.headline}>{item.headline}</Text>
            <Text style={[styles.headline, { color: Colors.accent }]}>{item.headline2}</Text>
            <Text style={styles.body}>{item.body}</Text>
          </View>
        )}
      />

      {/* Dots */}
      <View style={styles.dots}>
        {SLIDES.map((_, i) => (
          <View
            key={i}
            style={[styles.dot, i === currentIndex && styles.dotActive]}
          />
        ))}
      </View>

      <TouchableOpacity style={styles.cta} onPress={next} activeOpacity={0.85}>
        <LinearGradient
          colors={[Colors.accent, '#2da882']}
          style={styles.ctaGradient}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 0 }}
        >
          <Text style={styles.ctaText}>
            {currentIndex === SLIDES.length - 1 ? 'Get started' : 'Next'}
          </Text>
        </LinearGradient>
      </TouchableOpacity>

      <TouchableOpacity onPress={() => router.push('/signup')} style={styles.skip}>
        <Text style={styles.skipText}>Skip</Text>
      </TouchableOpacity>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  slide: {
    width,
    flex: 1,
    paddingHorizontal: Spacing.xl,
    justifyContent: 'center',
    paddingTop: 80,
  },
  icon: { fontSize: 56, marginBottom: Spacing.xl },
  headline: {
    fontSize: 36,
    fontFamily: 'Inter_700Bold',
    color: Colors.textPrimary,
    lineHeight: 44,
  },
  body: {
    ...Typography.body,
    color: Colors.textSecondary,
    marginTop: Spacing.lg,
    lineHeight: 26,
  },
  dots: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginBottom: Spacing.xl,
    gap: 6,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: Colors.border,
  },
  dotActive: {
    width: 20,
    backgroundColor: Colors.accent,
  },
  cta: {
    marginHorizontal: Spacing.xl,
    marginBottom: Spacing.md,
    borderRadius: Radius.lg,
    overflow: 'hidden',
  },
  ctaGradient: {
    paddingVertical: 18,
    alignItems: 'center',
  },
  ctaText: {
    fontSize: 17,
    fontFamily: 'Inter_600SemiBold',
    color: '#000',
  },
  skip: { alignItems: 'center', marginBottom: Spacing.xl },
  skipText: { ...Typography.small, color: Colors.textMuted },
});
