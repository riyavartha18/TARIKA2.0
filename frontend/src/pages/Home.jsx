import React, { useEffect } from 'react';
import Navbar from '../components/home/Navbar';
import HeroSlideshow from '../components/home/HeroSlideshow';
import CategoriesSection from '../components/home/CategoriesSection';
import PromoBanners from '../components/home/PromoBanners';
import TrendingSection from '../components/home/TrendingSection';
import NewArrivalsSection from '../components/home/NewArrivalsSection';
import CtaBanner from '../components/home/CtaBanner';
import FeatureFooter from '../components/home/FeatureFooter';
import '../styles/tarika.css';

export default function Home() {
  useEffect(() => {
    document.title = 'TARIKA — Style Your Story';
  }, []);

  return (
    <div className="tarika-home">
      {/* 1. Sticky Navigation Bar */}
      <Navbar />

      {/* 2 & 3. Hero & Auto-playing Slideshow */}
      <HeroSlideshow />

      {/* 4. 10 Horizontal Categories */}
      <CategoriesSection />

      {/* 5. Promotional Editorial Banners */}
      <PromoBanners />

      {/* 7. Trending Now Section */}
      <TrendingSection />

      {/* 6. New Arrivals Section */}
      <NewArrivalsSection />

      {/* Editorial Boutique Waiting for You Showcase */}
      <CtaBanner />

      {/* Feature Badges & Footer */}
      <FeatureFooter />
    </div>
  );
}
