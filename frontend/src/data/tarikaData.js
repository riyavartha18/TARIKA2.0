// Mock fashion data for TARIKA customer-facing homepage

export const HERO_SLIDES = [
  {
    id: 'slide-1',
    slideNum: '01',
    eyebrow: 'TARIKA HAUTE EDITORIAL',
    titleLine1: 'More Than',
    titleLine2: 'Fashion',
    scriptText: "It's You",
    description: 'Discover styles that move with you. Trendy. Timeless. Uniquely yours.',
    image: '/images/tarika_hero_pink_gown.jpg',
    badgeText: 'FASHION BEGINS WITH A FEELING',
    primaryCta: { label: 'Shop New Arrivals', href: '#new-arrivals' },
    secondaryCta: { label: 'Explore Sale', href: '#trending' },
    bgGradient: 'radial-gradient(ellipse at 70% 40%, #FDEEEB 0%, #FBF2F0 45%, #FAF7F5 100%)'
  },
  {
    id: 'slide-2',
    slideNum: '02',
    eyebrow: 'EXCLUSIVE SEASONAL CLEARANCE',
    titleLine1: 'UP TO',
    titleLine2: '70% OFF',
    scriptText: 'Grand Finale',
    description: 'Signature designer dresses, coats, and chic evening accessories at our lowest prices of the year.',
    image: '/images/tarika_promo_sale.jpg',
    badgeText: 'LIMITED RUN HAUTE STYLES',
    primaryCta: { label: 'Shop The Clearance', href: '#trending' },
    secondaryCta: { label: 'View All Deals', href: '#categories' },
    bgGradient: 'radial-gradient(ellipse at 70% 40%, #FCE8E6 0%, #FBF0ED 50%, #FAF7F5 100%)'
  },
  {
    id: 'slide-3',
    slideNum: '03',
    eyebrow: 'SPRING / SUMMER RUNWAY EDIT',
    titleLine1: 'NEW SEASON',
    titleLine2: 'NEW YOU',
    scriptText: 'Fresh Bloom',
    description: 'Bolder silhouettes, ethereal pastel hues, and hand-embroidered textures made to elevate your presence.',
    image: '/images/tarika_promo_new_season.jpg',
    badgeText: 'CURATED SS26 COLLECTION',
    primaryCta: { label: 'Explore The Lookbook', href: '#categories' },
    secondaryCta: { label: 'Shop Pastels', href: '#new-arrivals' },
    bgGradient: 'radial-gradient(ellipse at 70% 40%, #F9E7E5 0%, #FAF2EF 50%, #FAF7F5 100%)'
  },
  {
    id: 'slide-4',
    slideNum: '04',
    eyebrow: 'TIMELESS CAPSULE WARDROBE',
    titleLine1: 'EVERYDAY',
    titleLine2: 'ESSENTIALS',
    scriptText: 'Pure Comfort',
    description: 'Effortless knitwear, relaxed tailored blazers, and versatile separates designed for day-to-evening fluidity.',
    image: '/images/tarika_boutique_archway.jpg',
    badgeText: 'ORGANIC COTTON & SILK BLENDS',
    primaryCta: { label: 'Discover Essentials', href: '#new-arrivals' },
    secondaryCta: { label: 'Learn More', href: '#about' },
    bgGradient: 'radial-gradient(ellipse at 70% 40%, #FDEEE9 0%, #FDF4F0 50%, #FAF7F5 100%)'
  }
];

export const CATEGORIES = [
  {
    id: 'dresses',
    name: 'Dresses',
    image: 'https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=300&auto=format&fit=crop&q=80',
    count: '140+ Styles'
  },
  {
    id: 'tops',
    name: 'Tops',
    image: 'https://images.unsplash.com/photo-1564257631407-4deb1f99d992?w=300&auto=format&fit=crop&q=80',
    count: '95+ Styles'
  },
  {
    id: 'jeans',
    name: 'Jeans',
    image: 'https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=300&auto=format&fit=crop&q=80',
    count: '60+ Styles'
  },
  {
    id: 'jackets',
    name: 'Jackets',
    image: 'https://images.unsplash.com/photo-1551028719-00167b16eac5?w=300&auto=format&fit=crop&q=80',
    count: '45+ Styles'
  },
  {
    id: 'coords',
    name: 'Co-ords',
    image: 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=300&auto=format&fit=crop&q=80',
    count: '55+ Styles'
  },
  {
    id: 'activewear',
    name: 'Activewear',
    image: 'https://images.unsplash.com/photo-1518611012118-696072aa579a?w=300&auto=format&fit=crop&q=80',
    count: '40+ Styles'
  },
  {
    id: 'accessories',
    name: 'Accessories',
    image: 'https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=300&auto=format&fit=crop&q=80',
    count: '80+ Styles'
  },
  {
    id: 'footwear',
    name: 'Footwear',
    image: 'https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=300&auto=format&fit=crop&q=80',
    count: '65+ Styles'
  },
  {
    id: 'jewelry',
    name: 'Jewelry',
    image: 'https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=300&auto=format&fit=crop&q=80',
    count: '70+ Styles'
  },
  {
    id: 'bags',
    name: 'Bags',
    image: 'https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=300&auto=format&fit=crop&q=80',
    count: '50+ Styles'
  }
];

export const TRENDING_PRODUCTS = [
  {
    id: 'prod-trend-1',
    name: 'Floral Maxi Dress',
    price: 1899,
    originalPrice: 2499,
    badge: 'New',
    badgeType: 'new',
    image: 'https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?w=600&auto=format&fit=crop&q=85',
    category: 'Dresses',
    rating: 4.9,
    reviewsCount: 142
  },
  {
    id: 'prod-trend-2',
    name: 'Classic White Top',
    price: 999,
    originalPrice: 1399,
    badge: 'Best Seller',
    badgeType: 'bestseller',
    image: 'https://images.unsplash.com/photo-1534126511673-b6899657816a?w=600&auto=format&fit=crop&q=85',
    category: 'Tops',
    rating: 4.8,
    reviewsCount: 218
  },
  {
    id: 'prod-trend-3',
    name: 'Wide Leg Jeans',
    price: 1499,
    originalPrice: 1999,
    badge: null,
    image: 'https://images.unsplash.com/photo-1582418702059-97ebafb35d09?w=600&auto=format&fit=crop&q=85',
    category: 'Jeans',
    rating: 4.7,
    reviewsCount: 95
  },
  {
    id: 'prod-trend-4',
    name: 'Leather Jacket',
    price: 2499,
    originalPrice: 3499,
    badge: null,
    image: 'https://images.unsplash.com/photo-1521223890158-f9f7c3d5d504?w=600&auto=format&fit=crop&q=85',
    category: 'Jackets',
    rating: 4.9,
    reviewsCount: 167
  },
  {
    id: 'prod-trend-5',
    name: 'Pink Co-ord Set',
    price: 1999,
    originalPrice: 2699,
    badge: null,
    image: 'https://images.unsplash.com/photo-1509631179647-0177331693ae?w=600&auto=format&fit=crop&q=85',
    category: 'Co-ords',
    rating: 4.9,
    reviewsCount: 114
  },
  {
    id: 'prod-trend-6',
    name: 'Denim Dress',
    price: 1799,
    originalPrice: 2299,
    badge: 'New',
    badgeType: 'new',
    image: 'https://images.unsplash.com/photo-1529139574466-a303027c1d8b?w=600&auto=format&fit=crop&q=85',
    category: 'Dresses',
    rating: 4.8,
    reviewsCount: 88
  }
];

export const NEW_ARRIVALS = [
  {
    id: 'prod-na-1',
    name: 'Silk Organza Corset Gown',
    price: 3499,
    originalPrice: 4299,
    badge: 'New',
    badgeType: 'new',
    image: 'https://images.unsplash.com/photo-1566174053879-31528523f8ae?w=600&auto=format&fit=crop&q=85',
    category: 'Dresses',
    sizes: ['XS', 'S', 'M', 'L'],
    rating: 5.0
  },
  {
    id: 'prod-na-2',
    name: 'Cashmere Cable Knit Cardigan',
    price: 2199,
    originalPrice: 2799,
    badge: 'Trending',
    badgeType: 'bestseller',
    image: 'https://images.unsplash.com/photo-1620799140408-edc6dcb6d633?w=600&auto=format&fit=crop&q=85',
    category: 'Knitwear',
    sizes: ['S', 'M', 'L', 'XL'],
    rating: 4.9
  },
  {
    id: 'prod-na-3',
    name: 'Tailored Rose Blazer & Trouser',
    price: 3299,
    originalPrice: 4499,
    badge: 'Haute Pick',
    badgeType: 'new',
    image: 'https://images.unsplash.com/photo-1594938298603-c8148c4dae35?w=600&auto=format&fit=crop&q=85',
    category: 'Co-ords',
    sizes: ['XS', 'S', 'M', 'L'],
    rating: 4.9
  },
  {
    id: 'prod-na-4',
    name: 'Pleated Satin Slip Skirt',
    price: 1699,
    originalPrice: 2199,
    badge: 'Popular',
    badgeType: 'bestseller',
    image: 'https://images.unsplash.com/photo-1583496661160-fb5886a0aaaa?w=600&auto=format&fit=crop&q=85',
    category: 'Bottoms',
    sizes: ['S', 'M', 'L'],
    rating: 4.8
  },
  {
    id: 'prod-na-5',
    name: 'Quilted Blush Crossbody Bag',
    price: 1899,
    originalPrice: 2599,
    badge: 'Bestseller',
    badgeType: 'bestseller',
    image: 'https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=600&auto=format&fit=crop&q=85',
    category: 'Accessories',
    sizes: ['One Size'],
    rating: 4.9
  },
  {
    id: 'prod-na-6',
    name: 'Crystal Embellished Mule Heels',
    price: 2799,
    originalPrice: 3699,
    badge: 'Exclusive',
    badgeType: 'new',
    image: 'https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=600&auto=format&fit=crop&q=85',
    category: 'Footwear',
    sizes: ['36', '37', '38', '39', '40'],
    rating: 4.9
  }
];

export const TRUST_FEATURES = [
  {
    id: 'feat-1',
    title: 'Free Shipping',
    subtitle: 'On orders above ₹999',
    icon: 'Truck'
  },
  {
    id: 'feat-2',
    title: 'Easy Returns',
    subtitle: 'Hassle free 15-day return',
    icon: 'RotateCcw'
  },
  {
    id: 'feat-3',
    title: 'Secure Payments',
    subtitle: '100% safe & encrypted',
    icon: 'ShieldCheck'
  },
  {
    id: 'feat-4',
    title: '24/7 Support',
    subtitle: 'Dedicated fashion stylists',
    icon: 'Headphones'
  }
];
