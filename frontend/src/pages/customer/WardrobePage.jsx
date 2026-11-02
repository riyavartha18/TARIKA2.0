import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Calendar,
  BarChart2,
  Sliders,
  Plus,
  Trash2,
  Check,
  AlertCircle,
  X,
  Sparkles,
  ShoppingBag,
  Tag,
  ArrowRight,
  Upload,
  Camera,
  Image as ImageIcon,
  FolderPlus,
  RefreshCw,
  ExternalLink,
  ChevronRight,
  Info,
  CheckCircle2,
  Eye,
} from 'lucide-react';
import { useAuth } from '../../auth/AuthContext';
import {
  getWardrobeItems,
  uploadWardrobeItem,
  updateWardrobeItem,
  deleteWardrobeItem,
  importOrdersToWardrobe,
  getCompleteLook,
  getWardrobeOutfits,
  saveWardrobeOutfit,
  getWardrobeCollections,
  createWardrobeCollection,
  toggleWardrobeDisplayMode,
  reprocessWardrobeItem,
  confirmParsedItems,
  resolveMediaUrl
} from '../../services/api';
import { Link } from 'react-router-dom';
import { useCustomer } from '../../context/CustomerContext';

const FILTER_CHIPS = [
  { id: 'all', label: 'All', slot: null, sub: null },
  { id: 'tops', label: 'Tops', slot: 'top', sub: null },
  { id: 'bottoms', label: 'Bottoms', slot: 'bottom', sub: null },
  { id: 'dresses', label: 'Dresses & Jumpsuits', slot: 'one_piece', sub: 'dress' },
  { id: 'ethnic', label: 'Sarees & Lehengas', slot: 'one_piece', sub: 'saree' },
  { id: 'shoes', label: 'Shoes', slot: 'footwear', sub: null },
  { id: 'bags', label: 'Bags', slot: 'bag', sub: null },
  { id: 'accessories', label: 'Accessories', slot: 'accessory', sub: null },
  { id: 'outerwear', label: 'Outerwear', slot: 'top', sub: 'outerwear' },
];

export default function WardrobePage() {
  const { token, user } = useAuth();
  const { openProductDetail } = useCustomer();

  // Primary state
  const [activeTab, setActiveTab] = useState('clothes'); // 'clothes' | 'outfits' | 'collections'
  const [activeChip, setActiveChip] = useState('all');
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState('');
  const [toastMsg, setToastMsg] = useState('');

  // Modals & Sheets
  const [selectedItem, setSelectedItem] = useState(null); // Detail sheet
  const [isUploadSheetOpen, setIsUploadSheetOpen] = useState(false);
  const [isStatsModalOpen, setIsStatsModalOpen] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  // Upload state
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadPreview, setUploadPreview] = useState(null);
  const [uploadConsent, setUploadConsent] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const fileInputRef = useRef(null);

  // Detail & Editing state
  const [isEditingTags, setIsEditingTags] = useState(false);
  const [editFormData, setEditFormData] = useState({});
  const [updatingTags, setUpdatingTags] = useState(false);
  const [completeLookData, setCompleteLookData] = useState(null);
  const [completeLookError, setCompleteLookError] = useState(null);
  const [loadingCompleteLook, setLoadingCompleteLook] = useState(false);
  const [selectedGoesWithSlot, setSelectedGoesWithSlot] = useState('all');
  const [loadingMoreGoesWith, setLoadingMoreGoesWith] = useState(false);

  // Multi-item / Person Outfit Confirmation Modal State
  const [parsedPieces, setParsedPieces] = useState(null);
  const [parsedPiecesSelection, setParsedPiecesSelection] = useState({});
  const [isConfirmingParsed, setIsConfirmingParsed] = useState(false);

  // Outfits tab state
  const [outfits, setOutfits] = useState([]);
  const [selectedOutfitPieces, setSelectedOutfitPieces] = useState({
    top: null,
    bottom: null,
    one_piece: null,
    footwear: null,
    bag: null,
  });
  const [outfitVerdict, setOutfitVerdict] = useState(null);
  const [savingOutfit, setSavingOutfit] = useState(false);

  // Collections tab state
  const [collections, setCollections] = useState([]);
  const [newCollectionName, setNewCollectionName] = useState('');
  const [creatingCollection, setCreatingCollection] = useState(false);

  // Studio render and original-photo display state
  const [itemDisplayOverrides, setItemDisplayOverrides] = useState({});
  const [reprocessingItemId, setReprocessingItemId] = useState(null);

  const getItemImage = useCallback((item) => {
    if (!item) return '';
    const savedMode = itemDisplayOverrides[item.id] || item.display_mode;
    const mode = savedMode === 'original' ? 'original' : 'render';
    if (mode === 'original') {
      return item.original_image_url || item.image_url || item.flat_image_url;
    }
    return item.flat_image_url || item.thumb_url || item.image_url;
  }, [itemDisplayOverrides]);

  const handleToggleItemDisplay = async (e, item, targetMode = null) => {
    if (e && e.stopPropagation) e.stopPropagation();
    if (!item) return;
    const savedMode = itemDisplayOverrides[item.id] || item.display_mode;
    const currentMode = savedMode === 'original' ? 'original' : 'render';
    const nextMode = targetMode || (currentMode === 'render' ? 'original' : 'render');

    // Optimistic update
    setItemDisplayOverrides((prev) => ({ ...prev, [item.id]: nextMode }));
    if (selectedItem && selectedItem.id === item.id) {
      setSelectedItem((prev) => ({ ...prev, display_mode: nextMode }));
    }

    const res = await toggleWardrobeDisplayMode(token, item.id, nextMode);
    if (res.success && res.item) {
      setItems((prev) => prev.map((it) => (it.id === item.id ? { ...it, ...res.item } : it)));
      if (selectedItem && selectedItem.id === item.id) {
        setSelectedItem(res.item);
      }
      showToast(nextMode === 'original' ? 'Displaying original photo' : 'Displaying studio render');
    }
  };

  const handleReprocessItem = async (itemId) => {
    setReprocessingItemId(itemId);
    showToast('Re-crafting studio render...');
    const res = await reprocessWardrobeItem(token, itemId);
    setReprocessingItemId(null);
    if (res.success && res.item) {
      showToast('Studio render updated!');
      setItems((prev) => prev.map((it) => (it.id === itemId ? { ...it, ...res.item } : it)));
      if (selectedItem && selectedItem.id === itemId) {
        setSelectedItem(res.item);
      }
      setItemDisplayOverrides((prev) => ({ ...prev, [itemId]: 'render' }));
    } else {
      alert(res.error || 'Failed to reprocess studio render');
    }
  };

  // ---------------------------------------------------------------------------
  // Load Wardrobe Items
  // ---------------------------------------------------------------------------
  const fetchItems = useCallback(async () => {
    setLoading(true);
    setErrorMsg('');
    try {
      const chipObj = FILTER_CHIPS.find((c) => c.id === activeChip);
      const filters = {};
      if (chipObj?.slot) filters.slot_type = chipObj.slot;

      const res = await getWardrobeItems(token, filters);
      if (res.success) {
        let fetched = res.results || [];
        // Filter sub if specific
        if (chipObj?.sub) {
          fetched = fetched.filter(
            (it) => it.subtype === chipObj.sub || (chipObj.id === 'ethnic' && ['saree', 'lehenga', 'lehenga_set'].includes(it.subtype))
          );
        }
        setItems(fetched);
      } else {
        setErrorMsg(res.error || 'Failed to load wardrobe.');
      }
    } catch (e) {
      setErrorMsg('Failed to load wardrobe items.');
    } finally {
      setLoading(false);
    }
  }, [token, activeChip]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  // Load outfits & collections when tabs change
  useEffect(() => {
    if (activeTab === 'outfits') {
      getWardrobeOutfits(token).then((res) => {
        if (res.success) setOutfits(res.outfits || []);
      });
    } else if (activeTab === 'collections') {
      getWardrobeCollections(token).then((res) => {
        if (res.success) setCollections(res.collections || []);
      });
    }
  }, [activeTab, token]);

  // Keep selectedItem synchronized with fresh item list
  useEffect(() => {
    if (selectedItem) {
      const fresh = items.find((it) => it.id === selectedItem.id);
      if (fresh && fresh.display_mode !== selectedItem.display_mode) {
        setSelectedItem((prev) => ({ ...prev, ...fresh }));
      }
    }
  }, [items]);

  const showToast = (msg) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(''), 3500);
  };

  // ---------------------------------------------------------------------------
  // Upload Garment Handler
  // ---------------------------------------------------------------------------
  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      setUploadError('Please select a JPG, PNG, or WebP photo.');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setUploadError('Image size exceeds 5 MB limit.');
      return;
    }

    setUploadFile(file);
    setUploadPreview(URL.createObjectURL(file));
    setUploadError('');
  };

  const handleUploadSubmit = async () => {
    if (!uploadFile) {
      setUploadError('Please select or capture a photo first.');
      return;
    }
    if (!uploadConsent) {
      setUploadError('Please consent to AI garment tagging.');
      return;
    }

    setUploading(true);
    setUploadError('');

    const formData = new FormData();
    formData.append('image', uploadFile);

    const res = await uploadWardrobeItem(token, formData);
    setUploading(false);

    if (res.status === 'multi_item_detected' && Array.isArray(res.pieces) && res.pieces.length > 0) {
      setIsUploadSheetOpen(false);
      setUploadFile(null);
      setUploadPreview(null);
      setParsedPieces(res.pieces);
      const initialSelection = {};
      res.pieces.forEach((p, idx) => {
        initialSelection[p.temp_id ?? idx] = true;
      });
      setParsedPiecesSelection(initialSelection);
      return;
    }

    if (res.success) {
      showToast('Piece added to your wardrobe!');
      setIsUploadSheetOpen(false);
      setUploadFile(null);
      setUploadPreview(null);
      if (res.item) {
        setItemDisplayOverrides((prev) => ({ ...prev, [res.item.id]: 'render' }));
        setSelectedItem(res.item);
      }
      fetchItems();
    } else {
      setUploadError(res.error || 'Failed to process and tag photo.');
    }
  };

  const handleConfirmParsedPieces = async () => {
    if (!parsedPieces) return;
    const selected = parsedPieces.filter((p, idx) => parsedPiecesSelection[p.temp_id ?? idx]);
    if (selected.length === 0) {
      alert('Please select at least one garment piece to save.');
      return;
    }

    setIsConfirmingParsed(true);
    const res = await confirmParsedItems(token, selected);
    setIsConfirmingParsed(false);

    if (res.success) {
      showToast(`Added ${res.count || selected.length} pieces to your wardrobe!`);
      setParsedPieces(null);
      fetchItems();
    } else {
      alert(res.error || 'Failed to save pieces.');
    }
  };

  const handleLoadMoreGoesWith = async (slotKey) => {
    if (!selectedItem || loadingMoreGoesWith) return;
    setLoadingMoreGoesWith(true);
    const currentItems = completeLookData?.slots?.[slotKey]?.items || [];
    const offset = currentItems.length;
    try {
      const res = await getCompleteLook(token, selectedItem.id, 10000, slotKey, offset, 12);
      if (res.success && Array.isArray(res.items)) {
        setCompleteLookData((prev) => {
          if (!prev || !prev.slots) return prev;
          const existingSlot = prev.slots[slotKey] || { items: [] };
          return {
            ...prev,
            slots: {
              ...prev.slots,
              [slotKey]: {
                ...existingSlot,
                items: [...existingSlot.items, ...res.items],
                has_more: res.has_more,
                count: existingSlot.items.length + res.items.length
              },
            },
          };
        });
      }
    } finally {
      setLoadingMoreGoesWith(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Order History Auto-Import
  // ---------------------------------------------------------------------------
  const handleImportOrders = async () => {
    showToast('Importing pieces from delivered orders...');
    const res = await importOrdersToWardrobe(token);
    if (res.success) {
      showToast(res.message || `Imported ${res.imported_count || 0} pieces from orders.`);
      fetchItems();
    } else {
      showToast(res.error || 'No new delivered orders found to import.');
    }
  };

  // ---------------------------------------------------------------------------
  // Tile Detail & Edit
  // ---------------------------------------------------------------------------
  const handleOpenDetail = (item) => {
    setSelectedItem(item);
    setItemDisplayOverrides((prev) => ({
      ...prev,
      [item.id]: item.display_mode === 'original' ? 'original' : 'render',
    }));

    setEditFormData({
      slot_type: item.slot_type || 'top',
      subtype: item.subtype || 'other',
      formality: item.formality || 3,
      pattern: item.pattern || 'solid',
      style_family: item.style_family || 'western',
      season: item.season || 'all_season',
      dominant_colours: Array.isArray(item.dominant_colours)
        ? item.dominant_colours.join(', ')
        : item.dominant_colours || '',
    });
    setIsEditingTags(false);
    setCompleteLookData(null);
    setCompleteLookError(null);
    setSelectedGoesWithSlot('all');

    // Fetch complete look recommendations
    fetchCompleteLook(item.id);
  };

  const fetchCompleteLook = useCallback((itemId) => {
    if (!itemId) return;
    setLoadingCompleteLook(true);
    setCompleteLookError(null);
    getCompleteLook(token, itemId, 10000)
      .then((res) => {
        if (res.success) {
          setCompleteLookData(res);
          setCompleteLookError(null);
        } else {
          console.error(`[DigitalWardrobe] Goes With error for item #${itemId}:`, res.error);
          setCompleteLookError(res.error || 'Failed to generate styling pairings');
        }
      })
      .catch((err) => {
        console.error(`[DigitalWardrobe] Network error fetching Goes With for item #${itemId}:`, err);
        setCompleteLookError('Network error connecting to stylist service');
      })
      .finally(() => setLoadingCompleteLook(false));
  }, [token]);

  const handleSaveTags = async () => {
    if (!selectedItem) return;
    setUpdatingTags(true);

    const colors = editFormData.dominant_colours
      .split(',')
      .map((c) => c.trim().toLowerCase())
      .filter(Boolean);

    const patchPayload = {
      slot_type: editFormData.slot_type,
      subtype: editFormData.subtype,
      formality: parseInt(editFormData.formality, 10),
      pattern: editFormData.pattern,
      style_family: editFormData.style_family,
      season: editFormData.season,
      dominant_colours: colors,
      user_verified: true,
      needs_review: false,
    };

    const res = await updateWardrobeItem(token, selectedItem.id, patchPayload);
    setUpdatingTags(false);

    if (res.success) {
      showToast('Tags verified and updated!');
      setSelectedItem(res.item);
      setIsEditingTags(false);
      fetchItems();
    } else {
      alert(res.error || 'Failed to update tags.');
    }
  };

  const handleDeleteItem = async (itemId) => {
    if (!window.confirm('Delete this piece? Its cutouts and data will be permanently removed.')) return;
    const res = await deleteWardrobeItem(token, itemId);
    if (res.success) {
      showToast('Piece removed from wardrobe.');
      setSelectedItem(null);
      fetchItems();
    } else {
      alert(res.error || 'Failed to delete piece.');
    }
  };

  // ---------------------------------------------------------------------------
  // Outfits Evaluation
  // ---------------------------------------------------------------------------
  const handleValidateSelectedOutfit = () => {
    const pieces = selectedOutfitPieces;
    const hasTop = Boolean(pieces.top);
    const hasBot = Boolean(pieces.bottom);
    const hasOp = Boolean(pieces.one_piece);

    if (!hasOp && !(hasTop && hasBot)) {
      setOutfitVerdict({
        valid: false,
        reason: 'A complete look requires either a Top + Bottom, or a One-Piece dress/saree.',
      });
      return;
    }

    if (hasOp && (hasTop || hasBot)) {
      setOutfitVerdict({
        valid: false,
        reason: 'One-piece dresses and sarees cannot be paired with a separate top or bottom.',
      });
      return;
    }

    // Pattern statement clash check
    const pats = [
      pieces.top?.pattern,
      pieces.bottom?.pattern,
      pieces.one_piece?.pattern,
    ].filter(Boolean);
    const printedCount = pats.filter((p) =>
      ['printed', 'floral', 'geometric', 'striped', 'abstract'].some((k) => p.toLowerCase().includes(k))
    ).length;

    if (printedCount > 1) {
      setOutfitVerdict({
        valid: false,
        reason: 'Statement Clash: Avoid pairing two strongly printed garments in the same outfit.',
      });
      return;
    }

    // Formality gap check
    const forms = [
      pieces.top?.formality,
      pieces.bottom?.formality,
      pieces.one_piece?.formality,
      pieces.footwear?.formality,
    ].filter((f) => typeof f === 'number');

    if (forms.length > 1) {
      const minF = Math.min(...forms);
      const maxF = Math.max(...forms);
      if (maxF - minF > 2) {
        setOutfitVerdict({
          valid: false,
          reason: 'Formality Mismatch: Combining very casual and highly formal pieces causes style tension.',
        });
        return;
      }
    }

    setOutfitVerdict({
      valid: true,
      reason: '✓ This look harmonizes beautifully across formality, silhouette, and statement balance!',
    });
  };

  const handleSaveLook = async () => {
    if (!outfitVerdict?.valid) return;
    setSavingOutfit(true);

    const pieceIds = Object.values(selectedOutfitPieces)
      .filter(Boolean)
      .map((p) => p.id);

    const res = await saveWardrobeOutfit(token, {
      name: `Curated Look #${outfits.length + 1}`,
      wardrobe_item_ids: pieceIds,
      styling_notes: outfitVerdict.reason,
    });
    setSavingOutfit(false);

    if (res.success) {
      showToast('Outfit saved to your looks!');
      setOutfits((prev) => [res.outfit, ...prev]);
      setSelectedOutfitPieces({
        top: null,
        bottom: null,
        one_piece: null,
        footwear: null,
        bag: null,
      });
      setOutfitVerdict(null);
    } else {
      alert(res.error || 'Failed to save outfit.');
    }
  };

  const handleSuggestOutfit = () => {
    // Build outfit from wardrobe pieces
    const tops = items.filter((i) => i.slot_type === 'top');
    const bots = items.filter((i) => i.slot_type === 'bottom');
    const fws = items.filter((i) => i.slot_type === 'footwear');
    const bags = items.filter((i) => i.slot_type === 'bag');

    if (tops.length > 0 && bots.length > 0) {
      const t = tops[0];
      const b = bots[0];
      const fw = fws[0] || null;
      const bg = bags[0] || null;
      setSelectedOutfitPieces({
        top: t,
        bottom: b,
        one_piece: null,
        footwear: fw,
        bag: bg,
      });
      setOutfitVerdict({
        valid: true,
        reason: '✓ Cohesive capsule pairing generated from your personal pieces.',
      });
    } else {
      showToast('Need at least 1 top and 1 bottom to suggest an outfit.');
    }
  };

  return (
    <div
      className="digital-wardrobe-container"
      style={{
        maxWidth: '1280px',
        margin: '0 auto',
        padding: '1.25rem 1rem 6rem',
        minHeight: '100vh',
        backgroundColor: '#FAF9F8',
        fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      }}
    >
      {/* Toast Notification */}
      {toastMsg && (
        <div
          style={{
            position: 'fixed',
            bottom: '88px',
            left: '50%',
            transform: 'translateX(-50%)',
            backgroundColor: '#1F191B',
            color: '#FFFFFF',
            padding: '10px 20px',
            borderRadius: '999px',
            boxShadow: '0 8px 24px rgba(0,0,0,0.22)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            zIndex: 9999,
            fontSize: '0.88rem',
            animation: 'fadeIn 0.2s ease-out',
            whiteSpace: 'nowrap',
          }}
        >
          <Check size={16} color="#4ADE80" />
          <span>{toastMsg}</span>
        </div>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* 1. Header: "My Wardrobe" with Planner, Stats, Menu Icons              */}
      {/* --------------------------------------------------------------------- */}
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '1rem',
          padding: '0.25rem 0.5rem',
        }}
      >
        <div>
          <h1
            style={{
              fontSize: '1.75rem',
              fontWeight: 700,
              color: '#1F191B',
              margin: 0,
              letterSpacing: '-0.5px',
            }}
          >
            My Wardrobe
          </h1>
          <p style={{ margin: '2px 0 0', fontSize: '0.82rem', color: '#786F72' }}>
            {items.length} piece{items.length !== 1 ? 's' : ''} cataloged
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Outfit Planner Icon */}
          <Link
            to="/customer/smart-budget-stylist"
            title="Outfit Planner & Smart Budget Stylist"
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              backgroundColor: '#FFFFFF',
              border: '1px solid #E8E5E3',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#1F191B',
              textDecoration: 'none',
              boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
            }}
          >
            <Calendar size={18} />
          </Link>

          {/* Stats Icon */}
          <button
            onClick={() => setIsStatsModalOpen(true)}
            title="Wardrobe Analytics & Distribution"
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              backgroundColor: '#FFFFFF',
              border: '1px solid #E8E5E3',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#1F191B',
              cursor: 'pointer',
              boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
            }}
          >
            <BarChart2 size={18} />
          </button>

          {/* Menu Icon */}
          <button
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            title="Actions Menu"
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              backgroundColor: '#FFFFFF',
              border: '1px solid #E8E5E3',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#1F191B',
              cursor: 'pointer',
              boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
              position: 'relative',
            }}
          >
            <Sliders size={18} />
          </button>
        </div>
      </header>

      {/* Menu Dropdown Sheet */}
      {isMenuOpen && (
        <div
          style={{
            position: 'absolute',
            right: '1rem',
            top: '70px',
            backgroundColor: '#FFFFFF',
            borderRadius: '16px',
            boxShadow: '0 12px 36px rgba(0,0,0,0.14)',
            border: '1px solid #EADBDA',
            padding: '8px',
            zIndex: 100,
            width: '240px',
          }}
        >
          <button
            onClick={() => {
              handleImportOrders();
              setIsMenuOpen(false);
            }}
            style={{
              width: '100%',
              padding: '10px 14px',
              textAlign: 'left',
              backgroundColor: 'transparent',
              border: 'none',
              borderRadius: '10px',
              fontSize: '0.88rem',
              fontWeight: 500,
              color: '#1F191B',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#F7F5F4')}
            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
          >
            <RefreshCw size={15} color="#9C4146" />
            <span>Import from Orders</span>
          </button>

          <Link
            to="/customer/smart-budget-stylist"
            style={{
              width: '100%',
              padding: '10px 14px',
              textAlign: 'left',
              backgroundColor: 'transparent',
              border: 'none',
              borderRadius: '10px',
              fontSize: '0.88rem',
              fontWeight: 500,
              color: '#1F191B',
              textDecoration: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#F7F5F4')}
            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
          >
            <Sparkles size={15} color="#9C4146" />
            <span>Smart Budget Stylist</span>
          </Link>
        </div>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* 2. Top Tabs: Clothes | Outfits | Collections                          */}
      {/* --------------------------------------------------------------------- */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          borderBottom: '1px solid #E8E5E3',
          marginBottom: '1rem',
        }}
      >
        {[
          { id: 'clothes', label: 'Clothes' },
          { id: 'outfits', label: 'Outfits' },
          { id: 'collections', label: 'Collections' },
        ].map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                flex: 1,
                padding: '12px 0',
                border: 'none',
                backgroundColor: 'transparent',
                fontSize: '0.95rem',
                fontWeight: isActive ? 600 : 400,
                color: isActive ? '#1F191B' : '#786F72',
                borderBottom: isActive ? '2px solid #1F191B' : '2px solid transparent',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* ===================================================================== */}
      {/* TAB 1: CLOTHES                                                        */}
      {/* ===================================================================== */}
      {activeTab === 'clothes' && (
        <>
          {/* 3. Horizontal Scroll Filter Chips */}
          <div
            style={{
              display: 'flex',
              gap: '8px',
              overflowX: 'auto',
              paddingBottom: '12px',
              marginBottom: '12px',
              scrollbarWidth: 'none',
              msOverflowStyle: 'none',
            }}
          >
            {FILTER_CHIPS.map((chip) => {
              const isSelected = activeChip === chip.id;
              return (
                <button
                  key={chip.id}
                  onClick={() => setActiveChip(chip.id)}
                  style={{
                    padding: '7px 15px',
                    borderRadius: '999px',
                    border: isSelected ? '1px solid #1F191B' : '1px solid #EADBDA',
                    backgroundColor: isSelected ? '#1F191B' : '#FFFFFF',
                    color: isSelected ? '#FFFFFF' : '#4A3E42',
                    fontSize: '0.82rem',
                    fontWeight: isSelected ? 600 : 500,
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                    transition: 'all 0.15s ease',
                    boxShadow: isSelected ? '0 2px 6px rgba(0,0,0,0.12)' : 'none',
                  }}
                >
                  {chip.label}
                </button>
              );
            })}
          </div>

          {/* 4. Wardrobe grid: responsive auto-fill, consistent editorial proportions */}
          {loading ? (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))',
                gap: '16px',
              }}
            >
              {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
                <div
                  key={i}
                  style={{
                    borderRadius: '16px',
                    backgroundColor: '#FAF9F8',
                    border: '1px solid #ECE7E3',
                    overflow: 'hidden',
                    display: 'flex',
                    flexDirection: 'column',
                  }}
                >
                  <div
                    style={{
                      aspectRatio: '1 / 1',
                      backgroundColor: '#EFECE9',
                      animation: 'pulse 1.2s infinite ease-in-out',
                    }}
                  />
                  <div style={{ padding: '12px 14px', backgroundColor: '#FFFFFF' }}>
                    <div style={{ width: '70%', height: '14px', backgroundColor: '#EFECE9', borderRadius: '4px', marginBottom: '8px' }} />
                    <div style={{ width: '45%', height: '10px', backgroundColor: '#EFECE9', borderRadius: '4px' }} />
                  </div>
                </div>
              ))}
            </div>
          ) : items.length === 0 ? (
            /* Empty State */
            <div
              style={{
                backgroundColor: '#FFFFFF',
                borderRadius: '20px',
                padding: '3rem 1.5rem',
                textAlign: 'center',
                maxWidth: '460px',
                margin: '2rem auto',
                border: '1px dashed #D6CECE',
              }}
            >
              <div
                style={{
                  width: '64px',
                  height: '64px',
                  borderRadius: '50%',
                  backgroundColor: '#F5ECE9',
                  color: '#9C4146',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto 1.25rem',
                }}
              >
                <Sparkles size={28} />
              </div>
              <h3
                style={{
                  fontSize: '1.25rem',
                  fontWeight: 600,
                  color: '#1F191B',
                  margin: '0 0 0.5rem',
                }}
              >
                Your Digital Wardrobe is Empty
              </h3>
              <p style={{ color: '#786F72', fontSize: '0.88rem', margin: '0 0 1.5rem', lineHeight: 1.5 }}>
                Snap a photo of any garment or automatically import from delivered orders in your order history.
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <button
                  onClick={handleImportOrders}
                  style={{
                    backgroundColor: '#9C4146',
                    color: '#FFFFFF',
                    border: 'none',
                    borderRadius: '999px',
                    padding: '12px 20px',
                    fontSize: '0.9rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                  }}
                >
                  <RefreshCw size={16} />
                  <span>Import from My Orders</span>
                </button>
                <button
                  onClick={() => setIsUploadSheetOpen(true)}
                  style={{
                    backgroundColor: '#FFFFFF',
                    color: '#1F191B',
                    border: '1px solid #D1C5C7',
                    borderRadius: '999px',
                    padding: '12px 20px',
                    fontSize: '0.9rem',
                    fontWeight: 500,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                  }}
                >
                  <Plus size={16} />
                  <span>Add Your First Piece</span>
                </button>
              </div>
            </div>
          ) : (
            <div
              className="wardrobe-grid"
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))',
                gap: '16px',
              }}
            >
              {items.map((item) => {
                const activeImg = getItemImage(item);
                const resolvedImg = resolveMediaUrl(activeImg);
                const savedMode = itemDisplayOverrides[item.id] || item.display_mode;
                const currentMode = savedMode === 'original' ? 'original' : 'render';
                const isReprocessing = reprocessingItemId === item.id;

                return (
                  <div
                    key={item.id}
                    onClick={() => handleOpenDetail(item)}
                    style={{
                      borderRadius: '16px',
                      backgroundColor: '#FAF9F8',
                      border: '1px solid #ECE7E3',
                      position: 'relative',
                      overflow: 'hidden',
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                      boxShadow: '0 2px 10px rgba(0,0,0,0.03)',
                      transition: 'all 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.transform = 'translateY(-4px)';
                      e.currentTarget.style.boxShadow = '0 12px 28px -6px rgba(0,0,0,0.08)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.transform = 'translateY(0)';
                      e.currentTarget.style.boxShadow = '0 2px 10px rgba(0,0,0,0.03)';
                    }}
                  >
                    {/* Studio-render product canvas */}
                    <div
                      style={{
                        aspectRatio: '1 / 1',
                        width: '100%',
                        position: 'relative',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: '16px',
                        backgroundColor: '#FAF9F8',
                      }}
                    >
                      {/* Top-Left Mode Indicator Badge */}
                      <div
                        style={{
                          position: 'absolute',
                          top: '10px',
                          left: '10px',
                          zIndex: 2,
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          backgroundColor: 'rgba(255, 255, 255, 0.92)',
                          backdropFilter: 'blur(6px)',
                          padding: '3px 8px',
                          borderRadius: '999px',
                          fontSize: '0.68rem',
                          fontWeight: 600,
                          color: '#3A2E33',
                          boxShadow: '0 2px 6px rgba(0,0,0,0.04)',
                          border: '1px solid rgba(0,0,0,0.04)',
                        }}
                      >
                        {currentMode === 'original' ? (
                          <>
                            <Camera size={11} color="#6B5E63" />
                            <span>Original</span>
                          </>
                        ) : (
                          <>
                            <Sparkles size={11} color="#9C4146" />
                            <span>Studio Render</span>
                          </>
                        )}
                      </div>

                      {/* Top-Right Quick Toggle Button */}
                      <div
                        style={{
                          position: 'absolute',
                          top: '10px',
                          right: '10px',
                          zIndex: 2,
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                        }}
                      >
                        {item.needs_review && (
                          <div
                            title="Needs review: Low AI confidence. Tap to confirm tags."
                            style={{
                              width: '8px',
                              height: '8px',
                              borderRadius: '50%',
                              backgroundColor: '#F59E0B',
                              boxShadow: '0 0 0 2px #FFFFFF',
                            }}
                          />
                        )}

                        <button
                          type="button"
                          onClick={(e) => handleToggleItemDisplay(e, item)}
                          title={currentMode === 'original' ? 'Switch to Studio Render' : 'View Original Upload'}
                          style={{
                            width: '28px',
                            height: '28px',
                            borderRadius: '50%',
                            backgroundColor: 'rgba(255, 255, 255, 0.92)',
                            backdropFilter: 'blur(6px)',
                            border: '1px solid rgba(0,0,0,0.06)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            cursor: 'pointer',
                            color: '#4A3E42',
                            boxShadow: '0 2px 6px rgba(0,0,0,0.05)',
                          }}
                        >
                          {currentMode === 'original' ? <Sparkles size={13} color="#9C4146" /> : <Eye size={13} />}
                        </button>
                      </div>

                      {/* Studio-render garment image */}
                      {isReprocessing ? (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
                          <RefreshCw size={22} color="#9C4146" className="animate-spin" />
                          <span style={{ fontSize: '0.72rem', color: '#786F72' }}>Rendering...</span>
                        </div>
                      ) : (
                        <img
                          src={resolvedImg}
                          alt={item.item_name}
                          loading="lazy"
                          style={{
                            width: '100%',
                            height: '100%',
                            objectFit: 'contain',
                            display: 'block',
                            transition: 'transform 0.3s ease',
                          }}
                          onError={(e) => {
                            console.warn(`[WardrobeImage] Failed to load image URL for item #${item.id} (${item.item_name}):`, resolvedImg);
                            e.currentTarget.style.display = 'none';
                            if (e.currentTarget.nextSibling) {
                              e.currentTarget.nextSibling.style.display = 'flex';
                            }
                          }}
                        />
                      )}

                      {/* Fallback Placeholder on load failure */}
                      <div
                        style={{
                          display: 'none',
                          flexDirection: 'column',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: '#9C9295',
                          fontSize: '0.72rem',
                          textAlign: 'center',
                          padding: '4px',
                        }}
                      >
                        <ImageIcon size={24} />
                        <span style={{ marginTop: '4px' }}>Unavailable</span>
                      </div>
                    </div>

                    {/* Card Editorial Footer */}
                    <div
                      style={{
                        padding: '12px 14px 14px',
                        backgroundColor: '#FFFFFF',
                        borderTop: '1px solid #F0EEEB',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3px' }}>
                        <h4
                          style={{
                            margin: 0,
                            fontSize: '0.86rem',
                            fontWeight: 600,
                            color: '#1F191B',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            maxWidth: '72%',
                          }}
                        >
                          {item.item_name}
                        </h4>
                        <span
                          style={{
                            fontSize: '0.7rem',
                            color: '#9C4146',
                            fontWeight: 600,
                            textTransform: 'capitalize',
                          }}
                        >
                          {item.subtype || item.slot_type}
                        </span>
                      </div>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          fontSize: '0.72rem',
                          color: '#786F72',
                        }}
                      >
                        <span style={{ textTransform: 'capitalize' }}>
                          {item.slot_type === 'one_piece' ? 'One Piece' : item.slot_type}
                        </span>
                        <div style={{ display: 'flex', gap: '3px', alignItems: 'center' }}>
                          {[1, 2, 3, 4, 5].map((lvl) => (
                            <span
                              key={lvl}
                              style={{
                                width: '4px',
                                height: '4px',
                                borderRadius: '50%',
                                backgroundColor: lvl <= (item.formality || 3) ? '#9C4146' : '#E5E1DF',
                              }}
                            />
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* ===================================================================== */}
      {/* TAB 2: OUTFITS (SAVED LOOKS & VALIDATOR)                               */}
      {/* ===================================================================== */}
      {activeTab === 'outfits' && (
        <div style={{ padding: '0.5rem 0' }}>
          {/* Quick Actions */}
          <div style={{ display: 'flex', gap: '8px', marginBottom: '1.25rem' }}>
            <button
              onClick={handleSuggestOutfit}
              style={{
                flex: 1,
                padding: '12px 14px',
                borderRadius: '12px',
                backgroundColor: '#1F191B',
                color: '#FFFFFF',
                border: 'none',
                fontWeight: 600,
                fontSize: '0.88rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
              }}
            >
              <Sparkles size={16} />
              <span>Suggest an Outfit</span>
            </button>
            <Link
              to="/customer/smart-budget-stylist"
              style={{
                flex: 1,
                padding: '12px 14px',
                borderRadius: '12px',
                backgroundColor: '#FFFFFF',
                color: '#1F191B',
                border: '1px solid #D1C5C7',
                fontWeight: 600,
                fontSize: '0.88rem',
                textDecoration: 'none',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
              }}
            >
              <ShoppingBag size={16} color="#9C4146" />
              <span>Complete with Store</span>
            </Link>
          </div>

          {/* Interactive Outfit Canvas */}
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '16px',
              border: '1px solid #E8E5E3',
              padding: '1.25rem',
              marginBottom: '1.5rem',
            }}
          >
            <h3 style={{ fontSize: '1rem', fontWeight: 600, margin: '0 0 1rem', color: '#1F191B' }}>
              Outfit Harmonizer
            </h3>

            {/* Piece Selectors */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginBottom: '1rem' }}>
              {['top', 'bottom', 'footwear'].map((slotKey) => {
                const picked = selectedOutfitPieces[slotKey];
                const slotItems = items.filter((i) => i.slot_type === slotKey);
                return (
                  <div
                    key={slotKey}
                    style={{
                      aspectRatio: '1 / 1',
                      border: '1px dashed #D6CECE',
                      borderRadius: '12px',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      position: 'relative',
                      backgroundColor: picked ? '#FFFFFF' : '#FAFAF9',
                      padding: '6px',
                      overflow: 'hidden',
                    }}
                  >
                    {picked ? (
                      <>
                        <img
                          src={resolveMediaUrl(picked.thumb_url || picked.flat_image_url || picked.image_url)}
                          alt={picked.item_name}
                          style={{ width: '80%', height: '80%', objectFit: 'contain' }}
                          onError={(e) => {
                            console.warn(`[WardrobeImage] Failed to load outfit slot preview for item #${picked.id}:`, e.currentTarget.src);
                            e.currentTarget.style.display = 'none';
                          }}
                        />
                        <button
                          onClick={() => setSelectedOutfitPieces((prev) => ({ ...prev, [slotKey]: null }))}
                          style={{
                            position: 'absolute',
                            top: '4px',
                            right: '4px',
                            background: '#1F191B',
                            color: '#FFFFFF',
                            border: 'none',
                            borderRadius: '50%',
                            width: '20px',
                            height: '20px',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          <X size={12} />
                        </button>
                      </>
                    ) : (
                      <select
                        onChange={(e) => {
                          const it = items.find((x) => x.id === parseInt(e.target.value, 10));
                          setSelectedOutfitPieces((prev) => ({ ...prev, [slotKey]: it || null }));
                        }}
                        style={{
                          width: '100%',
                          height: '100%',
                          opacity: 0,
                          position: 'absolute',
                          cursor: 'pointer',
                        }}
                      >
                        <option value="">Select {slotKey}</option>
                        {slotItems.map((si) => (
                          <option key={si.id} value={si.id}>
                            {si.item_name}
                          </option>
                        ))}
                      </select>
                    )}
                    {!picked && (
                      <span style={{ fontSize: '0.75rem', color: '#786F72', textTransform: 'capitalize' }}>
                        + {slotKey}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>

            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                onClick={handleValidateSelectedOutfit}
                style={{
                  flex: 1,
                  padding: '10px 14px',
                  borderRadius: '10px',
                  backgroundColor: '#9C4146',
                  color: '#FFFFFF',
                  border: 'none',
                  fontWeight: 600,
                  fontSize: '0.84rem',
                  cursor: 'pointer',
                }}
              >
                Validate Look
              </button>
              {outfitVerdict?.valid && (
                <button
                  onClick={handleSaveLook}
                  disabled={savingOutfit}
                  style={{
                    padding: '10px 18px',
                    borderRadius: '10px',
                    backgroundColor: '#1F191B',
                    color: '#FFFFFF',
                    border: 'none',
                    fontWeight: 600,
                    fontSize: '0.84rem',
                    cursor: 'pointer',
                  }}
                >
                  Save Look
                </button>
              )}
            </div>

            {/* Verdict Display */}
            {outfitVerdict && (
              <div
                style={{
                  marginTop: '1rem',
                  padding: '10px 14px',
                  borderRadius: '10px',
                  backgroundColor: outfitVerdict.valid ? '#ECFDF5' : '#FEF2F2',
                  border: outfitVerdict.valid ? '1px solid #A7F3D0' : '1px solid #FECACA',
                  color: outfitVerdict.valid ? '#065F46' : '#991B1B',
                  fontSize: '0.84rem',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '8px',
                }}
              >
                {outfitVerdict.valid ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
                <span>{outfitVerdict.reason}</span>
              </div>
            )}
          </div>

          {/* Saved Outfits List */}
          <h3 style={{ fontSize: '1rem', fontWeight: 600, margin: '0 0 0.75rem', color: '#1F191B' }}>
            Saved Looks ({outfits.length})
          </h3>
          {outfits.length === 0 ? (
            <p style={{ color: '#786F72', fontSize: '0.88rem' }}>No outfits saved yet. Build and save your first ensemble above.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {outfits.map((of) => (
                <div
                  key={of.id}
                  style={{
                    backgroundColor: '#FFFFFF',
                    borderRadius: '12px',
                    border: '1px solid #E8E5E3',
                    padding: '12px',
                  }}
                >
                  <div style={{ fontWeight: 600, fontSize: '0.92rem', marginBottom: '4px' }}>{of.name}</div>
                  <div style={{ fontSize: '0.8rem', color: '#786F72', marginBottom: '8px' }}>
                    {of.styling_notes || 'Runway balanced combination.'}
                  </div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    {(of.items || of.wardrobe_items || []).map((wi) => (
                      <div
                        key={wi.id}
                        style={{
                          width: '48px',
                          height: '48px',
                          borderRadius: '8px',
                          backgroundColor: '#F5F2F0',
                          overflow: 'hidden',
                        }}
                      >
                        <img
                          src={resolveMediaUrl(wi.thumb_url || wi.flat_image_url || wi.image_url)}
                          alt={wi.item_name}
                          style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                          onError={(e) => {
                            console.warn(`[WardrobeImage] Failed to load saved outfit piece for item #${wi.id}:`, e.currentTarget.src);
                            e.currentTarget.style.display = 'none';
                          }}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ===================================================================== */}
      {/* TAB 3: COLLECTIONS                                                    */}
      {/* ===================================================================== */}
      {activeTab === 'collections' && (
        <div style={{ padding: '0.5rem 0' }}>
          {/* Create Collection Box */}
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '16px',
              border: '1px solid #E8E5E3',
              padding: '1.25rem',
              marginBottom: '1.5rem',
            }}
          >
            <h3 style={{ fontSize: '1rem', fontWeight: 600, margin: '0 0 0.5rem', color: '#1F191B' }}>
              Create Custom Collection
            </h3>
            <p style={{ fontSize: '0.82rem', color: '#786F72', margin: '0 0 1rem' }}>
              Organize garments into bespoke categories like "Office Formal", "Resort Vacation", or "Festive Wedding".
            </p>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                type="text"
                placeholder="Collection name (e.g. Minimalist Workwear)"
                value={newCollectionName}
                onChange={(e) => setNewCollectionName(e.target.value)}
                style={{
                  flex: 1,
                  padding: '10px 14px',
                  borderRadius: '10px',
                  border: '1px solid #D1C5C7',
                  fontSize: '0.88rem',
                }}
              />
              <button
                onClick={async () => {
                  if (!newCollectionName.trim()) return;
                  setCreatingCollection(true);
                  const res = await createWardrobeCollection(token, { name: newCollectionName.trim() });
                  setCreatingCollection(false);
                  if (res.success) {
                    showToast('Collection created!');
                    setNewCollectionName('');
                    setCollections((prev) => [res.collection, ...prev]);
                  }
                }}
                disabled={creatingCollection}
                style={{
                  backgroundColor: '#1F191B',
                  color: '#FFFFFF',
                  padding: '10px 18px',
                  borderRadius: '10px',
                  border: 'none',
                  fontWeight: 600,
                  fontSize: '0.88rem',
                  cursor: 'pointer',
                }}
              >
                Create
              </button>
            </div>
          </div>

          {/* Collections Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '12px' }}>
            {collections.length === 0 ? (
              <p style={{ color: '#786F72', fontSize: '0.88rem' }}>No collections yet.</p>
            ) : (
              collections.map((col) => (
                <div
                  key={col.id}
                  style={{
                    backgroundColor: '#FFFFFF',
                    borderRadius: '14px',
                    border: '1px solid #E8E5E3',
                    padding: '16px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                    <FolderPlus size={18} color="#9C4146" />
                    <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600 }}>{col.name}</h4>
                  </div>
                  <p style={{ margin: 0, fontSize: '0.8rem', color: '#786F72' }}>
                    {col.items_count || (col.items || []).length} piece{col.items_count !== 1 ? 's' : ''}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* 5. Floating "+" Button at Bottom Center                               */}
      {/* --------------------------------------------------------------------- */}
      <div
        style={{
          position: 'fixed',
          bottom: '24px',
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 90,
        }}
      >
        <button
          onClick={() => setIsUploadSheetOpen(true)}
          style={{
            width: '56px',
            height: '56px',
            borderRadius: '50%',
            backgroundColor: '#1F191B',
            color: '#FFFFFF',
            border: 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
            cursor: 'pointer',
            transition: 'transform 0.15s ease',
          }}
          onMouseDown={(e) => (e.currentTarget.style.transform = 'scale(0.92)')}
          onMouseUp={(e) => (e.currentTarget.style.transform = 'scale(1)')}
        >
          <Plus size={26} strokeWidth={2.5} />
        </button>
      </div>

      {/* --------------------------------------------------------------------- */}
      {/* UPLOAD BOTTOM SHEET                                                   */}
      {/* --------------------------------------------------------------------- */}
      {isUploadSheetOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            backdropFilter: 'blur(3px)',
            zIndex: 1000,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'flex-end',
          }}
          onClick={() => !uploading && setIsUploadSheetOpen(false)}
        >
          <div
            style={{
              backgroundColor: '#FFFFFF',
              width: '100%',
              maxWidth: '520px',
              borderTopLeftRadius: '24px',
              borderTopRightRadius: '24px',
              padding: '1.5rem',
              maxHeight: '90vh',
              overflowY: 'auto',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, color: '#1F191B' }}>
                Add Garment Photo
              </h2>
              <button
                onClick={() => setIsUploadSheetOpen(false)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#786F72' }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Tip Banner */}
            <div
              style={{
                backgroundColor: '#F5ECE9',
                borderRadius: '12px',
                padding: '12px',
                marginBottom: '1.25rem',
                display: 'flex',
                gap: '10px',
                alignItems: 'flex-start',
                color: '#4A3E42',
                fontSize: '0.84rem',
                lineHeight: 1.4,
              }}
            >
              <Info size={18} color="#9C4146" style={{ flexShrink: 0, marginTop: '2px' }} />
              <div>
                <strong>Photo Tip:</strong> Lay flat or hang it, against a plain background, with only one item per photo.
              </div>
            </div>

            {/* File Pickers */}
            <input
              type="file"
              ref={fileInputRef}
              accept="image/jpeg,image/png,image/webp"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
            />

            {!uploadPreview ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '1.25rem' }}>
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  style={{
                    border: '1px dashed #D1C5C7',
                    borderRadius: '16px',
                    padding: '1.75rem 1rem',
                    backgroundColor: '#FAF9F8',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '8px',
                    cursor: 'pointer',
                  }}
                >
                  <Camera size={26} color="#9C4146" />
                  <span style={{ fontSize: '0.88rem', fontWeight: 600, color: '#1F191B' }}>Take Photo</span>
                </button>

                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  style={{
                    border: '1px dashed #D1C5C7',
                    borderRadius: '16px',
                    padding: '1.75rem 1rem',
                    backgroundColor: '#FAF9F8',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '8px',
                    cursor: 'pointer',
                  }}
                >
                  <ImageIcon size={26} color="#9C4146" />
                  <span style={{ fontSize: '0.88rem', fontWeight: 600, color: '#1F191B' }}>Choose from Gallery</span>
                </button>
              </div>
            ) : (
              <div style={{ textAlign: 'center', marginBottom: '1.25rem' }}>
                <div
                  style={{
                    width: '180px',
                    height: '180px',
                    borderRadius: '16px',
                    overflow: 'hidden',
                    margin: '0 auto 10px',
                    border: '1px solid #E8E5E3',
                    backgroundColor: '#FFFFFF',
                  }}
                >
                  <img
                    src={uploadPreview}
                    alt="Preview"
                    style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                  />
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setUploadFile(null);
                    setUploadPreview(null);
                  }}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#9C4146',
                    fontSize: '0.82rem',
                    cursor: 'pointer',
                    textDecoration: 'underline',
                  }}
                >
                  Choose another photo
                </button>
              </div>
            )}

            {/* AI Consent Checkbox */}
            <label
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '10px',
                fontSize: '0.82rem',
                color: '#6B5E63',
                marginBottom: '1.25rem',
                cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={uploadConsent}
                onChange={(e) => setUploadConsent(e.target.checked)}
                style={{ marginTop: '3px' }}
              />
              <span>
                I consent to sending this garment photo to the configured vision AI provider for background removal and
                automatic styling tag classification.
              </span>
            </label>

            {uploadError && (
              <div
                style={{
                  color: '#DC2626',
                  fontSize: '0.84rem',
                  marginBottom: '1rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <AlertCircle size={15} />
                <span>{uploadError}</span>
              </div>
            )}

            <button
              onClick={handleUploadSubmit}
              disabled={uploading || !uploadFile}
              style={{
                width: '100%',
                padding: '14px',
                borderRadius: '12px',
                backgroundColor: '#1F191B',
                color: '#FFFFFF',
                border: 'none',
                fontWeight: 600,
                fontSize: '0.92rem',
                cursor: uploading || !uploadFile ? 'not-allowed' : 'pointer',
                opacity: uploading || !uploadFile ? 0.6 : 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
              }}
            >
              {uploading ? (
                <>
                  <RefreshCw size={18} className="animate-spin" />
                  <span>Removing background & creating studio render...</span>
                </>
              ) : (
                <>
                  <Upload size={18} />
                  <span>Upload & Auto-Tag Garment</span>
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* MULTI-GARMENT CONFIRMATION MODAL (Person Outfit Detection)            */}
      {/* --------------------------------------------------------------------- */}
      {parsedPieces && parsedPieces.length > 0 && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.6)',
            backdropFilter: 'blur(4px)',
            zIndex: 1100,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            padding: '1.25rem',
          }}
        >
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '24px',
              maxWidth: '620px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              padding: '1.75rem',
              boxShadow: '0 24px 60px rgba(0,0,0,0.22)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.25rem' }}>
              <div>
                <h2 style={{ fontSize: '1.35rem', fontWeight: 700, margin: '0 0 4px', color: '#1F191B' }}>
                  We found {parsedPieces.length} pieces in this photo
                </h2>
                <p style={{ margin: 0, fontSize: '0.84rem', color: '#786F72', lineHeight: 1.4 }}>
                  Each garment has been cleanly parsed from the photo with its own cutout, dominant colors, and styling tags.
                </p>
              </div>
              <button
                onClick={() => setParsedPieces(null)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#786F72', padding: '4px' }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Pieces list */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginBottom: '1.5rem' }}>
              {parsedPieces.map((piece, idx) => {
                const key = piece.temp_id ?? idx;
                const isSelected = parsedPiecesSelection[key] ?? true;
                return (
                  <div
                    key={key}
                    style={{
                      borderRadius: '16px',
                      border: isSelected ? '1.5px solid #9C4146' : '1px solid #E8E5E3',
                      padding: '14px',
                      backgroundColor: isSelected ? '#FDFAF9' : '#FFFFFF',
                      display: 'flex',
                      gap: '14px',
                      alignItems: 'flex-start',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={(e) =>
                        setParsedPiecesSelection((prev) => ({ ...prev, [key]: e.target.checked }))
                      }
                      title="Include in wardrobe"
                      style={{ marginTop: '8px', width: '18px', height: '18px', accentColor: '#9C4146', cursor: 'pointer' }}
                    />
                    <div
                      style={{
                        width: '90px',
                        height: '90px',
                        borderRadius: '12px',
                        backgroundColor: '#FAF9F8',
                        border: '1px solid #ECE7E3',
                        overflow: 'hidden',
                        flexShrink: 0,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: '6px',
                      }}
                    >
                      <img
                        src={resolveMediaUrl(piece.thumb_url || piece.image_url)}
                        alt={piece.item_name}
                        style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                      />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                        <input
                          type="text"
                          value={piece.item_name}
                          onChange={(e) => {
                            const val = e.target.value;
                            setParsedPieces((prev) =>
                              prev.map((p, i) => (i === idx ? { ...p, item_name: val } : p))
                            );
                          }}
                          style={{
                            fontSize: '0.96rem',
                            fontWeight: 700,
                            color: '#1F191B',
                            border: 'none',
                            borderBottom: '1px dashed #D1C5C7',
                            backgroundColor: 'transparent',
                            padding: '2px 0',
                            width: '100%',
                          }}
                        />
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '6px' }}>
                        <span
                          style={{
                            fontSize: '0.72rem',
                            backgroundColor: '#F5ECE9',
                            color: '#9C4146',
                            padding: '3px 8px',
                            borderRadius: '6px',
                            fontWeight: 600,
                            textTransform: 'capitalize',
                          }}
                        >
                          Slot: {piece.slot_type} ({piece.subtype})
                        </span>
                        {piece.dominant_colours?.map((col) => (
                          <span
                            key={col}
                            style={{
                              fontSize: '0.72rem',
                              backgroundColor: '#FAF9F8',
                              border: '1px solid #EADBDA',
                              color: '#4A3E42',
                              padding: '2px 8px',
                              borderRadius: '6px',
                              textTransform: 'capitalize',
                            }}
                          >
                            {col}
                          </span>
                        ))}
                      </div>
                      {piece.needs_review && (
                        <div
                          style={{
                            marginTop: '8px',
                            padding: '8px 10px',
                            borderRadius: '8px',
                            backgroundColor: '#FFFBEB',
                            border: '1px solid #FDE68A',
                            color: '#92400E',
                            fontSize: '0.76rem',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                          }}
                        >
                          <AlertCircle size={14} style={{ flexShrink: 0 }} />
                          <span>{piece.review_note || 'Part of this item is not visible. Retake a flat photo for the best result.'}</span>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Action buttons */}
            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                onClick={() => {
                  setParsedPieces(null);
                  setIsUploadSheetOpen(true);
                }}
                style={{
                  flex: 1,
                  padding: '12px',
                  borderRadius: '12px',
                  border: '1px solid #D1C5C7',
                  backgroundColor: '#FFFFFF',
                  color: '#4A3E42',
                  fontWeight: 600,
                  fontSize: '0.88rem',
                  cursor: 'pointer',
                }}
              >
                Retake
              </button>
              <button
                onClick={handleConfirmParsedPieces}
                disabled={isConfirmingParsed}
                style={{
                  flex: 2,
                  padding: '12px',
                  borderRadius: '12px',
                  border: 'none',
                  backgroundColor: '#1F191B',
                  color: '#FFFFFF',
                  fontWeight: 600,
                  fontSize: '0.88rem',
                  cursor: isConfirmingParsed ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                }}
              >
                {isConfirmingParsed ? (
                  <>
                    <RefreshCw size={16} className="animate-spin" />
                    <span>Saving selected garments...</span>
                  </>
                ) : (
                  <span>Confirm & Save Selected Pieces</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* 6. Item Detail Sheet (Tap on tile)                                    */}
      {/* --------------------------------------------------------------------- */}
      {selectedItem && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            backdropFilter: 'blur(3px)',
            zIndex: 1000,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'flex-end',
          }}
          onClick={() => setSelectedItem(null)}
        >
          <div
            style={{
              backgroundColor: '#FFFFFF',
              width: '100%',
              maxWidth: '560px',
              borderTopLeftRadius: '24px',
              borderTopRightRadius: '24px',
              padding: '1.5rem',
              maxHeight: '92vh',
              overflowY: 'auto',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span
                  style={{
                    backgroundColor: selectedItem.user_verified ? '#ECFDF5' : '#FEF3C7',
                    color: selectedItem.user_verified ? '#065F46' : '#92400E',
                    padding: '3px 10px',
                    borderRadius: '999px',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                  }}
                >
                  {selectedItem.user_verified ? 'Verified Tags' : 'AI Classified'}
                </span>
                {selectedItem.confidence && (
                  <span style={{ fontSize: '0.75rem', color: '#786F72' }}>
                    ({Math.round(selectedItem.confidence * 100)}% match)
                  </span>
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <button
                  onClick={() => handleDeleteItem(selectedItem.id)}
                  title="Delete piece"
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#DC2626',
                    cursor: 'pointer',
                    padding: '6px',
                  }}
                >
                  <Trash2 size={18} />
                </button>
                <button
                  onClick={() => setSelectedItem(null)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#786F72', padding: '6px' }}
                >
                  <X size={20} />
                </button>
              </div>
            </div>

            {/* Needs Review Banner if Low Confidence */}
            {selectedItem.needs_review && (
              <div
                style={{
                  backgroundColor: '#FFFBEB',
                  border: '1px solid #FDE68A',
                  color: '#92400E',
                  borderRadius: '12px',
                  padding: '12px',
                  marginBottom: '1rem',
                  fontSize: '0.84rem',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '8px',
                }}
              >
                <AlertCircle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
                <div>
                  <strong>Confirmation Needed:</strong>{' '}
                  {selectedItem.retake_prompt ||
                    'Vision confidence was under 60%. Please verify or edit the tags below before it can be used for outfit matching.'}
                </div>
              </div>
            )}

            {/* Display mode switcher: studio render or original photo */}
            {(() => {
              const matchedItem = items.find((it) => it.id === selectedItem.id);
              const savedMode = itemDisplayOverrides[selectedItem.id] || selectedItem.display_mode;
              const activeMode = savedMode === 'original' ? 'original' : 'render';
              const activeImage = getItemImage(selectedItem);
              const isReprocessing = reprocessingItemId === selectedItem.id;
              const hasOriginal = Boolean(selectedItem.original_image_url || matchedItem?.original_image_url);

              return (
                <div style={{ marginBottom: '1.25rem' }}>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginBottom: '10px',
                      gap: '8px',
                      flexWrap: 'wrap',
                    }}
                  >
                    {/* Two-way segmented control */}
                    <div
                      style={{
                        display: 'inline-flex',
                        backgroundColor: '#F3EFEA',
                        padding: '3px',
                        borderRadius: '10px',
                        gap: '2px',
                        flexWrap: 'wrap',
                      }}
                    >
                      {/* Studio render */}
                      <button
                        type="button"
                        onClick={(e) => handleToggleItemDisplay(e, selectedItem, 'render')}
                        style={{
                          padding: '6px 12px',
                          borderRadius: '8px',
                          border: 'none',
                          fontSize: '0.78rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                          backgroundColor: activeMode === 'render' ? '#FFFFFF' : 'transparent',
                          color: activeMode === 'render' ? '#1F191B' : '#786F72',
                          boxShadow: activeMode === 'render' ? '0 1px 4px rgba(0,0,0,0.08)' : 'none',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '5px',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        <Sparkles size={13} style={{ color: activeMode === 'render' ? '#9C4146' : '#786F72' }} />
                        <span>Studio Render</span>
                      </button>

                      {/* Original photo */}
                      <button
                        type="button"
                        onClick={(e) => handleToggleItemDisplay(e, selectedItem, 'original')}
                        disabled={!hasOriginal}
                        title={!hasOriginal ? 'Original upload photo is not retained for this piece' : 'Switch to raw original photo'}
                        style={{
                          padding: '6px 12px',
                          borderRadius: '8px',
                          border: 'none',
                          fontSize: '0.78rem',
                          fontWeight: 600,
                          cursor: !hasOriginal ? 'not-allowed' : 'pointer',
                          opacity: !hasOriginal ? 0.45 : 1,
                          backgroundColor: activeMode === 'original' ? '#FFFFFF' : 'transparent',
                          color: activeMode === 'original' ? '#1F191B' : '#786F72',
                          boxShadow: activeMode === 'original' ? '0 1px 4px rgba(0,0,0,0.08)' : 'none',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '5px',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        <Camera size={13} />
                        <span>Original</span>
                      </button>
                    </div>

                    {/* Secondary Actions */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      {activeMode === 'render' && (
                        <button
                          type="button"
                          onClick={() => handleReprocessItem(selectedItem.id)}
                          disabled={isReprocessing}
                          title="Re-run background removal and studio rendering"
                          style={{
                            background: '#FAF9F8',
                            border: '1px solid #E6E1DC',
                            borderRadius: '8px',
                            padding: '6px 12px',
                            fontSize: '0.76rem',
                            fontWeight: 600,
                            color: '#6B5E63',
                            cursor: isReprocessing ? 'not-allowed' : 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '5px',
                          }}
                        >
                          <RefreshCw size={12} className={isReprocessing ? 'animate-spin' : ''} />
                          <span>{isReprocessing ? 'Rendering...' : 'Re-craft Shot'}</span>
                        </button>
                      )}
                    </div>
                  </div>

                  {/* ========================================================================= */}
                  {/* VIEWPORT CONTAINER                                                        */}
                  {/* ========================================================================= */}

                  {/* Studio render or original photo canvas */}
                  <div
                      style={{
                        width: '100%',
                        aspectRatio: '1 / 1',
                        backgroundColor: '#FAF9F8',
                        backgroundImage: activeMode === 'render'
                          ? 'radial-gradient(circle at 50% 45%, #FFFFFF 0%, #FAF8F5 65%, #F0EAE1 100%)'
                          : 'none',
                        borderRadius: '16px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: '1.5rem',
                        position: 'relative',
                        overflow: 'hidden',
                        boxShadow: 'inset 0 0 16px rgba(0,0,0,0.02), 0 4px 16px rgba(0,0,0,0.03)',
                        border: '1px solid #ECE7E3',
                      }}
                    >
                      {/* Status Pill in corner */}
                      <div
                        style={{
                          position: 'absolute',
                          top: '12px',
                          left: '12px',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '5px',
                          backgroundColor: 'rgba(255, 255, 255, 0.92)',
                          backdropFilter: 'blur(6px)',
                          padding: '4px 10px',
                          borderRadius: '999px',
                          fontSize: '0.72rem',
                          fontWeight: 600,
                          color: activeMode === 'render' ? '#9C4146' : '#57534E',
                          boxShadow: '0 2px 6px rgba(0,0,0,0.06)',
                        }}
                      >
                        {activeMode === 'render' ? (
                          <>
                            <Sparkles size={11} color="#9C4146" />
                            <span>Studio Render</span>
                          </>
                        ) : (
                          <>
                            <Camera size={11} color="#57534E" />
                            <span>Original Upload</span>
                          </>
                        )}
                      </div>

                      <img
                        key={activeImage}
                        src={resolveMediaUrl(activeImage)}
                        alt={selectedItem.item_name}
                        style={{
                          width: '100%',
                          height: '100%',
                          objectFit: 'contain',
                          filter: activeMode === 'render'
                            ? 'drop-shadow(0 16px 24px rgba(28,25,23,0.12)) drop-shadow(0 4px 6px rgba(28,25,23,0.06))'
                            : 'none',
                          transition: 'filter 0.3s ease, transform 0.3s ease',
                        }}
                        onError={(e) => {
                          console.warn(`[WardrobeImage] Failed to load detail sheet image for item #${selectedItem.id} (${selectedItem.item_name}):`, e.currentTarget.src);
                          e.currentTarget.style.display = 'none';
                          if (e.currentTarget.nextSibling) {
                            e.currentTarget.nextSibling.style.display = 'flex';
                          }
                        }}
                      />
                      <div
                        style={{
                          display: 'none',
                          flexDirection: 'column',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: '#9C9295',
                          fontSize: '0.82rem',
                          textAlign: 'center',
                          padding: '1rem',
                        }}
                      >
                        <ImageIcon size={32} />
                        <span style={{ marginTop: '6px' }}>Image unavailable</span>
                      </div>
                  </div>
                </div>
              );
            })()}

            {/* Item Title */}
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: '0 0 1rem', color: '#1F191B' }}>
              {selectedItem.item_name}
            </h2>

            {/* Auto-detected tags with Edit Chips */}
            <div style={{ marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#786F72', textTransform: 'uppercase' }}>
                  Garment Attributes
                </span>
                <button
                  onClick={() => setIsEditingTags(!isEditingTags)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#9C4146',
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  {isEditingTags ? 'Cancel' : 'Edit Tags'}
                </button>
              </div>

              {!isEditingTags ? (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  <div
                    style={{
                      backgroundColor: '#F5ECE9',
                      padding: '5px 12px',
                      borderRadius: '8px',
                      fontSize: '0.82rem',
                      fontWeight: 500,
                      color: '#4A3E42',
                    }}
                  >
                    Slot: <strong>{selectedItem.slot_type}</strong>
                  </div>
                  <div
                    style={{
                      backgroundColor: '#F5ECE9',
                      padding: '5px 12px',
                      borderRadius: '8px',
                      fontSize: '0.82rem',
                      fontWeight: 500,
                      color: '#4A3E42',
                    }}
                  >
                    Subtype: <strong>{selectedItem.subtype}</strong>
                  </div>
                  <div
                    style={{
                      backgroundColor: '#F5ECE9',
                      padding: '5px 12px',
                      borderRadius: '8px',
                      fontSize: '0.82rem',
                      fontWeight: 500,
                      color: '#4A3E42',
                    }}
                  >
                    Formality: <strong>{selectedItem.formality}/5</strong>
                  </div>
                  <div
                    style={{
                      backgroundColor: '#F5ECE9',
                      padding: '5px 12px',
                      borderRadius: '8px',
                      fontSize: '0.82rem',
                      fontWeight: 500,
                      color: '#4A3E42',
                    }}
                  >
                    Pattern: <strong>{selectedItem.pattern}</strong>
                  </div>
                  <div
                    style={{
                      backgroundColor: '#F5ECE9',
                      padding: '5px 12px',
                      borderRadius: '8px',
                      fontSize: '0.82rem',
                      fontWeight: 500,
                      color: '#4A3E42',
                    }}
                  >
                    Style: <strong>{selectedItem.style_family}</strong>
                  </div>
                  {Array.isArray(selectedItem.dominant_colours) && selectedItem.dominant_colours.length > 0 && (
                    <div
                      style={{
                        backgroundColor: '#F5ECE9',
                        padding: '5px 12px',
                        borderRadius: '8px',
                        fontSize: '0.82rem',
                        fontWeight: 500,
                        color: '#4A3E42',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                      }}
                    >
                      <span>Colours:</span>
                      <strong>{selectedItem.dominant_colours.join(', ')}</strong>
                    </div>
                  )}
                </div>
              ) : (
                /* Edit Tags Form */
                <div
                  style={{
                    backgroundColor: '#FAF9F8',
                    padding: '12px',
                    borderRadius: '12px',
                    border: '1px solid #E8E5E3',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '10px',
                  }}
                >
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                    <div>
                      <label style={{ fontSize: '0.75rem', fontWeight: 600 }}>Slot Type</label>
                      <select
                        value={editFormData.slot_type}
                        onChange={(e) => setEditFormData({ ...editFormData, slot_type: e.target.value })}
                        style={{ width: '100%', padding: '6px', borderRadius: '6px', border: '1px solid #D1C5C7' }}
                      >
                        <option value="top">Top</option>
                        <option value="bottom">Bottom</option>
                        <option value="one_piece">One-Piece</option>
                        <option value="footwear">Footwear</option>
                        <option value="bag">Bag</option>
                        <option value="accessory">Accessory</option>
                      </select>
                    </div>

                    <div>
                      <label style={{ fontSize: '0.75rem', fontWeight: 600 }}>Formality (1-5)</label>
                      <select
                        value={editFormData.formality}
                        onChange={(e) => setEditFormData({ ...editFormData, formality: e.target.value })}
                        style={{ width: '100%', padding: '6px', borderRadius: '6px', border: '1px solid #D1C5C7' }}
                      >
                        <option value="1">1 - Ultra Casual</option>
                        <option value="2">2 - Casual</option>
                        <option value="3">3 - Smart Casual</option>
                        <option value="4">4 - Semi-Formal</option>
                        <option value="5">5 - Formal / Festive</option>
                      </select>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                    <div>
                      <label style={{ fontSize: '0.75rem', fontWeight: 600 }}>Pattern</label>
                      <select
                        value={editFormData.pattern}
                        onChange={(e) => setEditFormData({ ...editFormData, pattern: e.target.value })}
                        style={{ width: '100%', padding: '6px', borderRadius: '6px', border: '1px solid #D1C5C7' }}
                      >
                        <option value="solid">Solid</option>
                        <option value="printed">Printed</option>
                        <option value="floral">Floral</option>
                        <option value="embroidered">Embroidered</option>
                        <option value="striped">Striped</option>
                      </select>
                    </div>

                    <div>
                      <label style={{ fontSize: '0.75rem', fontWeight: 600 }}>Style Family</label>
                      <select
                        value={editFormData.style_family}
                        onChange={(e) => setEditFormData({ ...editFormData, style_family: e.target.value })}
                        style={{ width: '100%', padding: '6px', borderRadius: '6px', border: '1px solid #D1C5C7' }}
                      >
                        <option value="western">Western</option>
                        <option value="ethnic">Ethnic</option>
                        <option value="indo-western">Indo-Western</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label style={{ fontSize: '0.75rem', fontWeight: 600 }}>Colours (comma separated)</label>
                    <input
                      type="text"
                      value={editFormData.dominant_colours}
                      onChange={(e) => setEditFormData({ ...editFormData, dominant_colours: e.target.value })}
                      style={{ width: '100%', padding: '6px', borderRadius: '6px', border: '1px solid #D1C5C7' }}
                    />
                  </div>

                  <button
                    onClick={handleSaveTags}
                    disabled={updatingTags}
                    style={{
                      backgroundColor: '#1F191B',
                      color: '#FFFFFF',
                      padding: '8px',
                      borderRadius: '8px',
                      border: 'none',
                      fontWeight: 600,
                      fontSize: '0.84rem',
                      cursor: 'pointer',
                    }}
                  >
                    {updatingTags ? 'Saving...' : 'Confirm & Save Tags'}
                  </button>
                </div>
              )}
            </div>

            {/* "Goes With" Section: Wardrobe & Store Pairings */}
            <div style={{ marginBottom: '1.5rem' }}>
              <h3 style={{ fontSize: '0.95rem', fontWeight: 700, margin: '0 0 0.75rem', color: '#1F191B' }}>
                Goes With
              </h3>

              {loadingCompleteLook ? (
                <p style={{ fontSize: '0.84rem', color: '#786F72' }}>Analyzing harmonizing pieces...</p>
              ) : completeLookError ? (
                <div style={{ padding: '10px 12px', borderRadius: '8px', backgroundColor: '#FDF2F2', border: '1px solid #F8B4B4', color: '#9B1C1C', fontSize: '0.84rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span>{completeLookError}</span>
                  <button
                    onClick={() => fetchCompleteLook(selectedItem?.id)}
                    style={{ marginLeft: '12px', padding: '4px 10px', fontSize: '0.78rem', fontWeight: 600, backgroundColor: '#9B1C1C', color: '#FFF', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
                  >
                    Retry
                  </button>
                </div>
              ) : !completeLookData || (!(completeLookData.compatible_products || completeLookData.recommended_store_products)?.length && !completeLookData.matching_wardrobe_items?.length && (!completeLookData.slots || !Object.values(completeLookData.slots).some(s => s.count > 0))) ? (
                <p style={{ fontSize: '0.84rem', color: '#786F72' }}>No immediate pairing rules generated for this piece.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {/* From User's Wardrobe */}
                  {completeLookData.matching_wardrobe_items?.length > 0 && (
                    <div>
                      <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#9C4146' }}>
                        From Your Wardrobe:
                      </span>
                      <div style={{ display: 'flex', gap: '8px', overflowX: 'auto', marginTop: '6px' }}>
                        {completeLookData.matching_wardrobe_items.map((mw) => (
                          <div
                            key={mw.id}
                            style={{
                              width: '64px',
                              height: '64px',
                              borderRadius: '8px',
                              backgroundColor: '#FAF9F8',
                              border: '1px solid #EADBDA',
                              overflow: 'hidden',
                              flexShrink: 0,
                            }}
                          >
                            <img
                              src={resolveMediaUrl(mw.thumb_url || mw.flat_image_url || mw.image_url)}
                              alt={mw.item_name}
                              style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                              onError={(e) => {
                                console.warn(`[WardrobeImage] Failed to load matching wardrobe piece for item #${mw.id}:`, e.currentTarget.src);
                                e.currentTarget.style.display = 'none';
                              }}
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* From Store Products ("Goes With") Grouped by Slot */}
                  {completeLookData.slots && Object.keys(completeLookData.slots).length > 0 && (
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <span style={{ fontSize: '0.86rem', fontWeight: 700, color: '#1F191B' }}>
                          Matching TARIKA Pieces
                        </span>
                        <span style={{ fontSize: '0.74rem', color: '#786F72' }}>
                          Curated from whole catalogue
                        </span>
                      </div>

                      {/* Slot Tabs */}
                      <div style={{ display: 'flex', gap: '6px', overflowX: 'auto', marginBottom: '12px', paddingBottom: '4px' }}>
                        {[
                          { id: 'all', label: 'All Pairs' },
                          { id: 'bottoms', label: 'Bottoms' },
                          { id: 'shoes', label: 'Shoes' },
                          { id: 'bags', label: 'Bags' },
                          { id: 'outerwear', label: 'Layers' },
                        ].filter(t => t.id === 'all' || Boolean(completeLookData.slots[t.id]?.count)).map((tab) => {
                          const isActive = selectedGoesWithSlot === tab.id;
                          const slotCount = tab.id === 'all' ? null : completeLookData.slots[tab.id]?.count;
                          return (
                            <button
                              key={tab.id}
                              onClick={() => setSelectedGoesWithSlot(tab.id)}
                              style={{
                                padding: '5px 12px',
                                borderRadius: '20px',
                                border: isActive ? '1px solid #9C4146' : '1px solid #E8E5E3',
                                backgroundColor: isActive ? '#9C4146' : '#FAF9F8',
                                color: isActive ? '#FFFFFF' : '#4A3E42',
                                fontSize: '0.74rem',
                                fontWeight: isActive ? 600 : 500,
                                cursor: 'pointer',
                                whiteSpace: 'nowrap',
                                transition: 'all 0.15s ease',
                              }}
                            >
                              {tab.label} {slotCount !== null ? `(${slotCount})` : ''}
                            </button>
                          );
                        })}
                      </div>

                      {/* Slot Content */}
                      {Object.entries(completeLookData.slots)
                        .filter(([sKey]) => selectedGoesWithSlot === 'all' || selectedGoesWithSlot === sKey)
                        .map(([sKey, sData]) => {
                          const slotTitle = sKey === 'bottoms' ? 'Bottoms' : sKey === 'shoes' ? 'Footwear' : sKey === 'bags' ? 'Bags' : 'Layers / Outerwear';
                          const itemsList = sData.items || [];
                          if (itemsList.length === 0) return null;

                          return (
                            <div key={sKey} style={{ marginBottom: '16px' }}>
                              {selectedGoesWithSlot === 'all' && (
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                                  <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#9C4146', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                                    {slotTitle}
                                  </span>
                                  <span style={{ fontSize: '0.7rem', color: '#786F72' }}>
                                    {itemsList.length} styles
                                  </span>
                                </div>
                              )}

                              <div style={{ display: 'flex', gap: '12px', overflowX: 'auto', paddingBottom: '6px' }}>
                                {itemsList.map((sp) => {
                                  const displayPrice = Math.round(Number(sp.price ?? sp.discount_price ?? 999));
                                  const reasonList = Array.isArray(sp.reasons) && sp.reasons.length > 0 ? sp.reasons : [sp.match_reason || sp.reason || 'Curated aesthetic complement'];
                                  const primaryR = reasonList[0];
                                  const secondaryR = reasonList[1] || null;

                                  return (
                                    <div
                                      key={sp.product_id || sp.id}
                                      onClick={() => openProductDetail(sp.product_id || sp.id)}
                                      title={`View ${sp.product_name} in store`}
                                      style={{
                                        width: '150px',
                                        borderRadius: '14px',
                                        border: '1px solid #E8E5E3',
                                        overflow: 'hidden',
                                        flexShrink: 0,
                                        backgroundColor: '#FFFFFF',
                                        cursor: 'pointer',
                                        transition: 'all 0.18s ease',
                                        boxShadow: '0 2px 6px rgba(0,0,0,0.04)',
                                        display: 'flex',
                                        flexDirection: 'column',
                                      }}
                                      onMouseEnter={(e) => {
                                        e.currentTarget.style.transform = 'translateY(-2px)';
                                        e.currentTarget.style.boxShadow = '0 6px 14px rgba(156,65,70,0.12)';
                                        e.currentTarget.style.borderColor = '#9C4146';
                                      }}
                                      onMouseLeave={(e) => {
                                        e.currentTarget.style.transform = 'none';
                                        e.currentTarget.style.boxShadow = '0 2px 6px rgba(0,0,0,0.04)';
                                        e.currentTarget.style.borderColor = '#E8E5E3';
                                      }}
                                    >
                                      <div style={{ height: '125px', backgroundColor: '#FAF9F8', position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                        <img
                                          src={resolveMediaUrl(sp.image)}
                                          alt={sp.product_name}
                                          style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'cover' }}
                                          onError={(e) => {
                                            e.currentTarget.style.display = 'none';
                                          }}
                                        />
                                        {sp.match_percentage && (
                                          <div
                                            style={{
                                              position: 'absolute',
                                              top: '6px',
                                              right: '6px',
                                              backgroundColor: 'rgba(255,255,255,0.94)',
                                              backdropFilter: 'blur(3px)',
                                              color: '#9C4146',
                                              fontSize: '0.64rem',
                                              fontWeight: 700,
                                              padding: '2px 6px',
                                              borderRadius: '6px',
                                              boxShadow: '0 2px 4px rgba(0,0,0,0.06)',
                                            }}
                                          >
                                            {sp.match_percentage}% Match
                                          </div>
                                        )}
                                      </div>
                                      <div style={{ padding: '8px 10px', display: 'flex', flexDirection: 'column', flex: 1 }}>
                                        <div
                                          style={{
                                            fontSize: '0.74rem',
                                            fontWeight: 600,
                                            whiteSpace: 'nowrap',
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis',
                                            color: '#1F191B',
                                          }}
                                        >
                                          {sp.product_name || sp.name}
                                        </div>
                                        <div style={{ fontSize: '0.78rem', color: '#9C4146', fontWeight: 700, marginTop: '2px' }}>
                                          Rs.{displayPrice}
                                        </div>
                                        <div style={{ fontSize: '0.64rem', color: '#6B5E63', lineHeight: 1.25, marginTop: '5px', flex: 1 }}>
                                          <div style={{ fontWeight: 500, color: '#4A3E42' }}>• {primaryR}</div>
                                          {secondaryR && (
                                            <div style={{ fontSize: '0.62rem', color: '#8A7D82', marginTop: '2px' }}>
                                              • {secondaryR}
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    </div>
                                  );
                                })}

                                {/* Show more button within this slot */}
                                {sData.has_more && (
                                  <div
                                    onClick={() => handleLoadMoreGoesWith(sKey)}
                                    style={{
                                      width: '120px',
                                      flexShrink: 0,
                                      backgroundColor: '#FAF9F8',
                                      borderRadius: '14px',
                                      border: '1px dashed #D1C5C7',
                                      display: 'flex',
                                      flexDirection: 'column',
                                      alignItems: 'center',
                                      justifyContent: 'center',
                                      cursor: loadingMoreGoesWith ? 'wait' : 'pointer',
                                      padding: '10px',
                                      textAlign: 'center',
                                    }}
                                    onMouseEnter={(e) => {
                                      e.currentTarget.style.backgroundColor = '#F5ECE9';
                                      e.currentTarget.style.borderColor = '#9C4146';
                                    }}
                                    onMouseLeave={(e) => {
                                      e.currentTarget.style.backgroundColor = '#FAF9F8';
                                      e.currentTarget.style.borderColor = '#D1C5C7';
                                    }}
                                  >
                                    <Sparkles size={18} color="#9C4146" style={{ marginBottom: '6px' }} />
                                    <span style={{ fontSize: '0.76rem', fontWeight: 600, color: '#1F191B' }}>
                                      {loadingMoreGoesWith ? 'Loading...' : 'Show More'}
                                    </span>
                                    <span style={{ fontSize: '0.64rem', color: '#786F72', marginTop: '2px' }}>
                                      Next {slotTitle}
                                    </span>
                                  </div>
                                )}
                              </div>
                            </div>
                          );
                        })}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Smart Budget Stylist Call-To-Action */}
            <Link
              to={`/customer/smart-budget-stylist?wardrobe_items=${selectedItem.id}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                width: '100%',
                padding: '12px',
                borderRadius: '12px',
                backgroundColor: '#9C4146',
                color: '#FFFFFF',
                textDecoration: 'none',
                fontWeight: 600,
                fontSize: '0.88rem',
              }}
            >
              <Sparkles size={16} />
              <span>Style Outfits with this Locked Piece (Rs.0)</span>
            </Link>
          </div>
        </div>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* 7. Stats Modal                                                        */}
      {/* --------------------------------------------------------------------- */}
      {isStatsModalOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1rem',
          }}
          onClick={() => setIsStatsModalOpen(false)}
        >
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '20px',
              padding: '1.5rem',
              maxWidth: '420px',
              width: '100%',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700 }}>Wardrobe Distribution</h3>
              <button onClick={() => setIsStatsModalOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.88rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Total Pieces Cataloged:</span>
                <strong>{items.length}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Verified Pieces:</span>
                <strong style={{ color: '#065F46' }}>{items.filter((i) => i.user_verified).length}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Needs Review:</span>
                <strong style={{ color: '#F59E0B' }}>{items.filter((i) => i.needs_review).length}</strong>
              </div>
              <hr style={{ border: 'none', borderTop: '1px solid #E8E5E3', margin: '8px 0' }} />
              {['top', 'bottom', 'one_piece', 'footwear', 'bag', 'accessory'].map((s) => (
                <div key={s} style={{ display: 'flex', justifyContent: 'space-between', textTransform: 'capitalize' }}>
                  <span>{s.replace('_', ' ')}s:</span>
                  <span>{items.filter((i) => i.slot_type === s).length}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
