from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase
from django.urls import reverse, resolve
from rest_framework.test import APIRequestFactory

from catalog.models import Category, Product, Inventory, Review, OrderItem
from catalog.serializers import (
    CategorySerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    CATEGORY_IMAGE_MAPPING
)
from catalog.services import CatalogService
from catalog.views import (
    CategoryListView,
    ProductListView,
    ProductDetailView,
    NewArrivalsView,
    TrendingView,
    SaleView
)


class CatalogURLRoutingTests(SimpleTestCase):
    """Test URL routing for all Part 2A Customer Catalog endpoints."""

    def test_categories_url_resolves(self):
        url = reverse('catalog:category-list')
        self.assertEqual(url, '/api/catalog/categories/')
        self.assertEqual(resolve(url).func.view_class, CategoryListView)

    def test_products_list_url_resolves(self):
        url = reverse('catalog:product-list')
        self.assertEqual(url, '/api/catalog/products/')
        self.assertEqual(resolve(url).func.view_class, ProductListView)

    def test_product_detail_url_resolves(self):
        url = reverse('catalog:product-detail', kwargs={'product_id': 'prod-123'})
        self.assertEqual(url, '/api/catalog/products/prod-123/')
        self.assertEqual(resolve(url).func.view_class, ProductDetailView)

    def test_new_arrivals_url_resolves(self):
        url = reverse('catalog:new-arrivals')
        self.assertEqual(url, '/api/catalog/new-arrivals/')
        self.assertEqual(resolve(url).func.view_class, NewArrivalsView)

    def test_trending_url_resolves(self):
        url = reverse('catalog:trending')
        self.assertEqual(url, '/api/catalog/trending/')
        self.assertEqual(resolve(url).func.view_class, TrendingView)

    def test_sale_url_resolves(self):
        url = reverse('catalog:sale')
        self.assertEqual(url, '/api/catalog/sale/')
        self.assertEqual(resolve(url).func.view_class, SaleView)


class CatalogSerializerTests(SimpleTestCase):
    """Test serialization, stock calculation, and image resolution."""

    def test_category_serializer_with_image(self):
        category = Category(
            category_id='cat-1',
            category_name='Dresses',
            description="Women's dresses",
            created_at='2025-01-01'
        )
        category.product_count = 42
        serializer = CategorySerializer(category)
        data = serializer.data

        self.assertEqual(data['category_id'], 'cat-1')
        self.assertEqual(data['category_name'], 'Dresses')
        self.assertEqual(data['product_count'], 42)
        self.assertEqual(data['image'], CATEGORY_IMAGE_MAPPING['dresses'])

    def test_category_serializer_without_image(self):
        category = Category(
            category_id='cat-2',
            category_name='Unknown Category',
            description="Special items",
            created_at='2025-01-01'
        )
        serializer = CategorySerializer(category)
        data = serializer.data
        self.assertIsNone(data['image'])

    def test_product_list_serializer_in_stock(self):
        category = Category(category_id='cat-1', category_name='Dresses')
        product = Product(
            product_id='prod-1',
            product_name='Silk Slip Dress',
            category=category,
            sku='D-001',
            description='Elegant silk dress',
            gender='women',
            color='Emerald',
            size='M',
            material='Silk',
            base_price=2500,
            selling_price=2200,
            launch_date='2025-06-01',
            is_active=True
        )
        product.total_stock_annotated = 45

        serializer = ProductListSerializer(product)
        data = serializer.data

        self.assertEqual(data['product_id'], 'prod-1')
        self.assertEqual(data['category_name'], 'Dresses')
        self.assertEqual(data['total_stock'], 45)
        self.assertTrue(data['in_stock'])
        self.assertEqual(data['image'], CATEGORY_IMAGE_MAPPING['dresses'])

    def test_product_list_serializer_out_of_stock(self):
        product = Product(
            product_id='prod-2',
            product_name='Sold Out Dress',
            sku='D-002',
            selling_price=1500,
            is_active=True
        )
        product.total_stock_annotated = 0

        serializer = ProductListSerializer(product)
        data = serializer.data

        self.assertEqual(data['total_stock'], 0)
        self.assertFalse(data['in_stock'])

    def test_product_detail_serializer_complete_schema(self):
        category = Category(category_id='cat-1', category_name='Dresses', description="Dresses desc")
        product = Product(
            product_id='prod-detail-1',
            product_name='Haute Gown',
            category=category,
            manufacturer_id='mfg-1',
            sku='G-999',
            description='Exquisite couture gown',
            gender='women',
            color='Rose Gold',
            size='S',
            material='Chiffon',
            cost_price=1200,
            base_price=3500,
            selling_price=3200,
            launch_date='2025-07-01',
            is_active=True,
            created_at='2025-07-01',
            updated_at='2025-07-10'
        )
        product.total_stock_annotated = 12

        serializer = ProductDetailSerializer(product)
        data = serializer.data

        # Verify every schema field is present
        self.assertEqual(data['product_id'], 'prod-detail-1')
        self.assertEqual(data['manufacturer_id'], 'mfg-1')
        self.assertEqual(data['sku'], 'G-999')
        self.assertEqual(data['cost_price'], 1200)
        self.assertEqual(data['base_price'], 3500)
        self.assertEqual(data['selling_price'], 3200)
        self.assertEqual(data['category']['category_name'], 'Dresses')
        self.assertEqual(data['total_stock'], 12)
        self.assertTrue(data['in_stock'])
        self.assertIn('inventory_breakdown', data)
        self.assertIn('rating_summary', data)


class CatalogViewsAPITests(SimpleTestCase):
    """Test API views using APIRequestFactory and public permissions."""
    databases = {'default'}

    def setUp(self):
        self.factory = APIRequestFactory()

    @patch('catalog.views.Category.objects.filter')
    def test_categories_endpoint_public_access(self, mock_filter):
        mock_qs = MagicMock()
        mock_qs.annotate.return_value.order_by.return_value = [
            Category(category_id='cat-1', category_name='Dresses', description='Dresses', created_at='2025-01-01'),
            Category(category_id='cat-2', category_name='Jeans', description='Jeans', created_at='2025-01-01'),
        ]
        mock_filter.return_value = mock_qs

        request = self.factory.get('/api/catalog/categories/')
        view = CategoryListView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['category_name'], 'Dresses')

    @patch('catalog.services.CatalogService.filter_and_sort_products')
    def test_products_endpoint_pagination_structure(self, mock_filter):
        mock_product = Product(
            product_id='p-1',
            product_name='Summer T-Shirt',
            sku='T-100',
            selling_price=499,
            is_active=True
        )
        mock_product.total_stock_annotated = 20

        mock_qs = MagicMock()
        mock_qs.count.return_value = 25
        mock_qs.__len__.return_value = 25
        mock_qs.__getitem__.side_effect = lambda s: [mock_product] * min(12, max(0, (s.stop or 25) - (s.start or 0)))
        mock_filter.return_value = mock_qs

        request = self.factory.get('/api/catalog/products/?page=1&page_size=12')
        view = ProductListView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn('count', response.data)
        self.assertIn('total_pages', response.data)
        self.assertIn('current_page', response.data)
        self.assertIn('page_size', response.data)
        self.assertIn('results', response.data)
        self.assertEqual(response.data['count'], 25)
        self.assertEqual(response.data['total_pages'], 3)
        self.assertEqual(response.data['current_page'], 1)

    @patch('catalog.services.CatalogService.filter_and_sort_products')
    def test_products_endpoint_filtering_parameters_passed(self, mock_filter):
        mock_qs = MagicMock()
        mock_qs.count.return_value = 0
        mock_qs.__len__.return_value = 0
        mock_qs.__getitem__.return_value = []
        mock_filter.return_value = mock_qs

        request = self.factory.get('/api/catalog/products/?category=Dresses&search=silk&min_price=500&max_price=2000&sort=price_low_high')
        view = ProductListView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 200)
        mock_filter.assert_called_once_with(
            category='Dresses',
            search='silk',
            min_price='500',
            max_price='2000',
            sort='price_low_high'
        )

    @patch('catalog.views.get_object_or_404')
    def test_product_detail_endpoint_success(self, mock_get_404):
        product = Product(
            product_id='p-100',
            product_name='Classic Kurti',
            sku='K-100',
            selling_price=1299,
            is_active=True
        )
        product.total_stock_annotated = 15
        mock_get_404.return_value = product

        request = self.factory.get('/api/catalog/products/p-100/')
        view = ProductDetailView.as_view()
        response = view(request, product_id='p-100')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['product_id'], 'p-100')
        self.assertEqual(response.data['product_name'], 'Classic Kurti')
        self.assertTrue(response.data['in_stock'])
        self.assertEqual(response.data['total_stock'], 15)

    @patch('catalog.services.CatalogService.get_new_arrivals')
    def test_new_arrivals_endpoint(self, mock_new):
        mock_product = Product(product_id='p-new', product_name='New Gown', selling_price=3000, is_active=True)
        mock_product.total_stock_annotated = 5
        mock_new.return_value = [mock_product]

        request = self.factory.get('/api/catalog/new-arrivals/?limit=8')
        view = NewArrivalsView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['product_id'], 'p-new')
        mock_new.assert_called_once_with(limit=8)

    @patch('catalog.services.CatalogService.get_trending')
    def test_trending_endpoint(self, mock_trend):
        mock_product = Product(product_id='p-trend', product_name='Trending Top', selling_price=999, is_active=True)
        mock_product.total_stock_annotated = 100
        mock_trend.return_value = [mock_product]

        request = self.factory.get('/api/catalog/trending/?limit=6')
        view = TrendingView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['product_id'], 'p-trend')
        mock_trend.assert_called_once_with(limit=6)

    @patch('catalog.services.CatalogService.get_sale_products')
    def test_sale_endpoint(self, mock_sale):
        mock_product = Product(product_id='p-sale', product_name='Sale Jacket', selling_price=1499, base_price=2999, is_active=True)
        mock_product.total_stock_annotated = 25
        mock_sale.return_value = [mock_product]

        request = self.factory.get('/api/catalog/sale/?limit=5')
        view = SaleView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['product_id'], 'p-sale')
        mock_sale.assert_called_once_with(limit=5)

    @patch('catalog.views.Category.objects.annotate')
    def test_grouped_category_products_endpoint(self, mock_annotate):
        mock_qs = MagicMock()
        mock_qs.filter.return_value.order_by.return_value.prefetch_related.return_value = [
            Category(category_id='cat-1', category_name='Dresses', description='Dresses')
        ]
        mock_annotate.return_value = mock_qs

        request = self.factory.get('/api/catalog/grouped-products/')
        from catalog.views import GroupedCategoryProductsView
        view = GroupedCategoryProductsView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['categories'][0]['category_name'], 'Dresses')


class CatalogServiceFilterSortingTests(SimpleTestCase):
    """Test sorting option resolution in CatalogService."""

    def test_sorting_options_mapping(self):
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs

        # Test 'newest'
        CatalogService.filter_and_sort_products(queryset=mock_qs, sort='newest')
        mock_qs.order_by.assert_called_with('-launch_date', '-created_at', 'product_id')

        # Test 'price_low_high'
        CatalogService.filter_and_sort_products(queryset=mock_qs, sort='price_low_high')
        mock_qs.order_by.assert_called_with('dim_selling_price', 'product_name', 'product_id')

        # Test 'price_high_low'
        CatalogService.filter_and_sort_products(queryset=mock_qs, sort='price_high_low')
        mock_qs.order_by.assert_called_with('-dim_selling_price', 'product_name', 'product_id')

        # Test 'name'
        CatalogService.filter_and_sort_products(queryset=mock_qs, sort='name')
        mock_qs.order_by.assert_called_with('product_name', 'product_id')
