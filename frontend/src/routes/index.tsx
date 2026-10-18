import { createFileRoute } from '@tanstack/react-router'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')
const API = `${API_BASE}/api/v1`
const CONVERSATION_STORAGE_KEY = 'thai-naturals-conversation'
const LANGUAGE_STORAGE_KEY = 'thai-naturals-language'

type Product = {
  id: string
  name: string
  category: string
  description: string
  ingredients: string[]
  benefits: string[]
  skin_types: string[]
  concerns: string[]
  how_to_use: string
  precautions: string
  price: number
  original_price: number
  stock_quantity: number
  image_url?: string
  is_active: boolean
  rating: number
  review_count: number
}

type ProductCard = {
  id: string
  name: string
  category: string
  description: string
  benefits: string[]
  price: number
  original_price?: number
  stock_quantity?: number
  image_url?: string
  availability?: string
}

type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
  order?: { id: string; payment_url: string; payment_status: string; order_status: string }
  clientId?: string
  pending?: boolean
  failed?: boolean
}

type Language = 'en' | 'ta' | 'ml' | 'hi'

const LANGUAGES: { value: Language; label: string; nativeName: string }[] = [
  { value: 'en', label: 'English', nativeName: 'English' },
  { value: 'ta', label: 'Tamil', nativeName: 'தமிழ்' },
  { value: 'ml', label: 'Malayalam', nativeName: 'മലയാളം' },
  { value: 'hi', label: 'Hindi', nativeName: 'हिन्दी' },
]

const CHAT_COPY: Record<Language, {
  navAssistant: string
  navProducts: string
  navCart: string
  navOrders: string
  newChat: string
  eyebrow: string
  titleFirst: string
  titleSecond: string
  intro: string
  assistant: string
  welcome: string
  recommendations: string
  suggestions: [string, string, string]
  placeholder: string
  send: string
  disclaimer: string
  typing: string
  sending: string
  failed: string
  retry: string
  language: string
}> = {
  en: {
    navAssistant: 'Assistant', navProducts: 'Product catalog', navCart: 'Your cart', navOrders: 'Orders & tracking',
    newChat: 'New chat', eyebrow: 'YOUR PERSONAL SKINCARE GUIDE', titleFirst: 'Good skincare starts',
    titleSecond: 'with a conversation.', intro: 'Tell me what your skin needs. I’ll help you explore the Thai Naturals range.',
    assistant: 'THAI NATURALS ASSISTANT',
    welcome: 'Hi there! 👋 Welcome to Thai Naturals. I’m here to help you find skincare that fits your skin and your routine. What are you looking to improve today?',
    recommendations: 'A FEW OPTIONS FOR YOU',
    suggestions: ['I have oily skin', 'Help with acne marks', 'Build me a simple routine'],
    placeholder: 'Ask about your skin, products, or routine…', send: 'Send message',
    disclaimer: 'Product information is demo catalog data. For skin concerns, consult a qualified professional.',
    typing: 'Thinking…', sending: 'Sending…', failed: 'Message not sent.', retry: 'Retry', language: 'Language',
  },
  ta: {
    navAssistant: 'உதவியாளர்', navProducts: 'தயாரிப்புகள்', navCart: 'உங்கள் கூடை', navOrders: 'ஆர்டர்கள் & கண்காணிப்பு',
    newChat: 'புதிய உரையாடல்', eyebrow: 'உங்கள் தனிப்பட்ட சருமப் பராமரிப்பு வழிகாட்டி', titleFirst: 'நல்ல சருமப் பராமரிப்பு',
    titleSecond: 'ஒரு உரையாடலில் தொடங்குகிறது.', intro: 'உங்கள் சருமத்திற்குத் தேவையானதைச் சொல்லுங்கள். Thai Naturals தயாரிப்புகளைத் தேர்ந்தெடுக்க உதவுகிறேன்.',
    assistant: 'THAI NATURALS உதவியாளர்',
    welcome: 'வணக்கம்! 👋 Thai Naturals-க்கு வரவேற்கிறோம். உங்கள் சருமத்திற்கும் தினசரி பராமரிப்பிற்கும் ஏற்ற தயாரிப்புகளைத் தேர்ந்தெடுக்க உதவுகிறேன். இன்று எதை மேம்படுத்த விரும்புகிறீர்கள்?',
    recommendations: 'உங்களுக்கான சில தேர்வுகள்',
    suggestions: ['எனக்கு எண்ணெய்ப்பசை சருமம் உள்ளது', 'முகப்பரு தழும்புகளுக்கு உதவுங்கள்', 'எளிய சருமப் பராமரிப்பு முறையைச் சொல்லுங்கள்'],
    placeholder: 'சருமம், தயாரிப்புகள் அல்லது பராமரிப்பு முறையைப் பற்றி கேளுங்கள்…', send: 'செய்தி அனுப்பு',
    disclaimer: 'தயாரிப்பு விவரங்கள் மாதிரி பட்டியலிலிருந்து எடுக்கப்பட்டவை. சருமப் பிரச்சினைகளுக்கு தகுதியான நிபுணரை அணுகவும்.',
    typing: 'பதில் தயாராகிறது…', sending: 'அனுப்பப்படுகிறது…', failed: 'செய்தி அனுப்பப்படவில்லை.', retry: 'மீண்டும் முயற்சி', language: 'மொழி',
  },
  ml: {
    navAssistant: 'സഹായി', navProducts: 'ഉൽപ്പന്നങ്ങൾ', navCart: 'നിങ്ങളുടെ കാർട്ട്', navOrders: 'ഓർഡറുകളും ട്രാക്കിംഗും',
    newChat: 'പുതിയ ചാറ്റ്', eyebrow: 'നിങ്ങളുടെ വ്യക്തിഗത ചർമ്മപരിചരണ സഹായി', titleFirst: 'നല്ല ചർമ്മപരിചരണം',
    titleSecond: 'ഒരു സംഭാഷണത്തിൽ തുടങ്ങുന്നു.', intro: 'നിങ്ങളുടെ ചർമ്മത്തിന് എന്താണ് വേണ്ടതെന്ന് പറയൂ. Thai Naturals ഉൽപ്പന്നങ്ങൾ കണ്ടെത്താൻ ഞാൻ സഹായിക്കാം.',
    assistant: 'THAI NATURALS സഹായി',
    welcome: 'നമസ്കാരം! 👋 Thai Naturals-ലേക്ക് സ്വാഗതം. നിങ്ങളുടെ ചർമ്മത്തിനും ദിനചര്യയ്ക്കും അനുയോജ്യമായ ഉൽപ്പന്നങ്ങൾ കണ്ടെത്താൻ ഞാൻ സഹായിക്കാം. ഇന്ന് എന്താണ് മെച്ചപ്പെടുത്താൻ ആഗ്രഹിക്കുന്നത്?',
    recommendations: 'നിങ്ങൾക്കായി ചില ഓപ്ഷനുകൾ',
    suggestions: ['എനിക്ക് എണ്ണമയമുള്ള ചർമ്മമാണ്', 'മുഖക്കുരു പാടുകൾക്ക് സഹായിക്കൂ', 'ലളിതമായ ദിനചര്യ നിർദേശിക്കൂ'],
    placeholder: 'ചർമ്മം, ഉൽപ്പന്നങ്ങൾ, ദിനചര്യ എന്നിവയെക്കുറിച്ച് ചോദിക്കൂ…', send: 'സന്ദേശം അയയ്ക്കുക',
    disclaimer: 'ഉൽപ്പന്ന വിവരങ്ങൾ ഡെമോ കാറ്റലോഗിൽ നിന്നുള്ളതാണ്. ചർമ്മപ്രശ്നങ്ങൾക്ക് യോഗ്യതയുള്ള വിദഗ്ധനെ സമീപിക്കുക.',
    typing: 'മറുപടി തയ്യാറാക്കുന്നു…', sending: 'അയയ്ക്കുന്നു…', failed: 'സന്ദേശം അയച്ചില്ല.', retry: 'വീണ്ടും ശ്രമിക്കുക', language: 'ഭാഷ',
  },
  hi: {
    navAssistant: 'सहायक', navProducts: 'उत्पाद सूची', navCart: 'आपकी कार्ट', navOrders: 'ऑर्डर और ट्रैकिंग',
    newChat: 'नई चैट', eyebrow: 'आपका व्यक्तिगत स्किनकेयर गाइड', titleFirst: 'अच्छी स्किनकेयर की शुरुआत',
    titleSecond: 'बातचीत से होती है।', intro: 'अपनी त्वचा की ज़रूरत बताइए। Thai Naturals के उत्पादों में से चुनने में मैं मदद करूँगा।',
    assistant: 'THAI NATURALS सहायक',
    welcome: 'नमस्ते! 👋 Thai Naturals में आपका स्वागत है। आपकी त्वचा और दिनचर्या के लिए सही स्किनकेयर चुनने में मैं मदद करूँगा। आज आप किस चीज़ में सुधार चाहते हैं?',
    recommendations: 'आपके लिए कुछ विकल्प',
    suggestions: ['मेरी त्वचा तैलीय है', 'मुंहासों के दागों में मदद करें', 'एक आसान स्किनकेयर रूटीन सुझाएँ'],
    placeholder: 'त्वचा, उत्पादों या रूटीन के बारे में पूछें…', send: 'संदेश भेजें',
    disclaimer: 'उत्पाद की जानकारी डेमो कैटलॉग से है। त्वचा संबंधी समस्या के लिए योग्य विशेषज्ञ से सलाह लें।',
    typing: 'जवाब तैयार हो रहा है…', sending: 'भेजा जा रहा है…', failed: 'संदेश नहीं भेजा गया।', retry: 'फिर कोशिश करें', language: 'भाषा',
  },
}

type CartEntry = { product_id: string; quantity: number }
type Cart = Record<string, CartEntry>
type Order = {
  id: string
  total: number
  currency: string
  order_status: string
  payment_status: string
  created_at?: string
  customer_name?: string
  email?: string
  phone?: string
  shipping_address?: string
  payment_url?: string
  tracking_url?: string
  tracking_number?: string
  items: { product_id: string; product_name: string; quantity: number; unit_price: number; line_total: number }[]
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API}${path}`, {
      ...init,
      headers: {
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
        ...init?.headers,
      },
    })
  } catch {
    throw new Error(`Can't reach the API at ${API_BASE}. Start the FastAPI server and check VITE_API_BASE_URL.`)
  }

  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = payload?.detail
    throw new Error(typeof detail === 'string' ? detail : detail?.message || payload?.message || `Request failed (${response.status})`)
  }
  return payload as T
}

function money(amount: number, currency = 'INR') {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 0 }).format(amount)
}

function shortDate(value?: string) {
  if (!value) return 'just now'
  return new Date(value).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

function renderMessageContent(content: string) {
  return content.split(/(\*\*.+?\*\*|https?:\/\/[^\s<>()]+)/gs).map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index}>{part.slice(2, -2)}</strong>
    }
    if (/^https?:\/\//i.test(part)) {
      const url = part.replace(/[.,!?;:]+$/, '')
      const trailingPunctuation = part.slice(url.length)
      return <span key={index}><a href={url} target="_blank" rel="noreferrer">{url}</a>{trailingPunctuation}</span>
    }
    return part
  })
}

export const Route = createFileRoute('/')({ component: Home })

function Home() {
  const [activeView, setActiveView] = useState<'chat' | 'products' | 'cart' | 'orders'>('chat')
  const [language, setLanguage] = useState<Language>('en')
  const [conversationId, setConversationId] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [productCards, setProductCards] = useState<ProductCard[]>([])
  const [allProducts, setAllProducts] = useState<Product[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [cart, setCart] = useState<Cart>({})
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [skinType, setSkinType] = useState('')
  const [concern, setConcern] = useState('')
  const [maxPrice, setMaxPrice] = useState('')
  const [chatInput, setChatInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [catalogLoading, setCatalogLoading] = useState(false)
  const [apiStatus, setApiStatus] = useState<'checking' | 'online' | 'offline'>('checking')
  const [error, setError] = useState('')
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [latestOrder, setLatestOrder] = useState<Order | null>(null)
  const [activeOrders, setActiveOrders] = useState<Order[]>([])
  const [orderHistory, setOrderHistory] = useState<Order[]>([])
  const [orderIdInput, setOrderIdInput] = useState('')
  const [tracking, setTracking] = useState<Record<string, any> | null>(null)
  const [busyAction, setBusyAction] = useState('')
  const messageEndRef = useRef<HTMLDivElement>(null)
  const currency = 'INR'
  const copy = CHAT_COPY[language]

  const productById = useMemo(() => new Map(allProducts.map((product) => [product.id, product])), [allProducts])
  const countInCart = Object.values(cart).reduce((total, entry) => total + entry.quantity, 0)
  const cartItems = Object.values(cart).flatMap((entry) => {
    const product = productById.get(entry.product_id)
    return product ? [{ product, quantity: entry.quantity }] : []
  })

  async function openProduct(productId: string) {
    try {
      const product = productById.get(productId) || (await apiRequest<{ product: Product }>(`/products/${encodeURIComponent(productId)}`)).product
      setAllProducts((current) => current.some((item) => item.id === product.id) ? current : [...current, product])
      setSelectedProduct(product)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not load product details.')
    }
  }

  const refreshProducts = useCallback(async (
    searchTerm = '',
    selectedCategory = '',
    selectedSkinType = '',
    selectedConcern = '',
    selectedMaxPrice = '',
  ) => {
    setCatalogLoading(true)
    try {
      const params = new URLSearchParams()
      if (searchTerm.trim()) params.set('q', searchTerm.trim())
      if (selectedCategory) params.set('category', selectedCategory)
      if (selectedSkinType) params.set('skin_type', selectedSkinType)
      if (selectedConcern) params.set('concern', selectedConcern)
      if (selectedMaxPrice && Number(selectedMaxPrice) > 0) params.set('max_price', selectedMaxPrice)
      const response = await apiRequest<{ products: Product[] }>(`/products${params.size ? `/search?${params.toString()}` : ''}`)
      setProducts(response.products)
      if (!params.size) setAllProducts(response.products)
      return response.products
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not load products.')
      return []
    } finally {
      setCatalogLoading(false)
    }
  }, [])

  const refreshCart = useCallback(async (id = conversationId) => {
    if (!id) return {}
    const response = await apiRequest<{ cart: Cart }>(`/cart/${encodeURIComponent(id)}`)
    setCart(response.cart)
    return response.cart
  }, [conversationId])

  const refreshOrders = useCallback(async () => {
    const result = await apiRequest<{ active_orders: Order[]; order_history: Order[] }>('/orders')
    setActiveOrders(result.active_orders)
    setOrderHistory(result.order_history)
    setLatestOrder((current) => (
      (current && result.order_history.find((order) => order.id === current.id))
      || result.active_orders[0]
      || result.order_history[0]
      || null
    ))
    return result
  }, [])

  const loadHistory = useCallback(async (id: string) => {
    const response = await apiRequest<{ conversation_id: string; messages: ChatMessage[] }>(`/chat/${encodeURIComponent(id)}/history`)
    setMessages(response.messages)
    const cartResponse = await apiRequest<{ cart: Cart }>(`/cart/${encodeURIComponent(id)}`)
    setCart(cartResponse.cart)
  }, [])

  useEffect(() => {
    let mounted = true
    const storedLanguage = window.localStorage.getItem(LANGUAGE_STORAGE_KEY)
    if (storedLanguage && LANGUAGES.some((item) => item.value === storedLanguage)) {
      setLanguage(storedLanguage as Language)
    }
    void fetch(`${API_BASE}/health`).then((response) => {
      if (!response.ok) throw new Error('Health check failed')
      if (mounted) setApiStatus('online')
    }).catch(() => {
      if (mounted) setApiStatus('offline')
    })
    void refreshProducts()
    const storedConversation = window.localStorage.getItem(CONVERSATION_STORAGE_KEY)
    if (storedConversation) {
      setConversationId(storedConversation)
      void loadHistory(storedConversation).catch(() => {
        window.localStorage.removeItem(CONVERSATION_STORAGE_KEY)
        setConversationId('')
        setMessages([])
        setCart({})
      })
    }
    window.localStorage.removeItem('thai-naturals-orders')
    return () => { mounted = false }
  }, [loadHistory, refreshProducts])

  useEffect(() => {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language)
  }, [language])

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, loading])

  useEffect(() => {
    if (activeView !== 'orders') return
    void refreshOrders().catch((cause) => {
      setError(cause instanceof Error ? cause.message : 'Could not load order history.')
    })
  }, [activeView, refreshOrders])

  async function ensureConversation() {
    if (conversationId) return conversationId
    const greeting = language === 'ta'
      ? 'வணக்கம்!'
      : language === 'ml'
        ? 'നമസ്കാരം!'
        : language === 'hi'
          ? 'नमस्ते!'
          : 'Hi there!'
    const result = await apiRequest<{ conversation_id: string; response: string; product_cards?: ProductCard[] }>('/chat', {
      method: 'POST',
      body: JSON.stringify({ message: greeting, language }),
    })
    setConversationId(result.conversation_id)
    window.localStorage.setItem(CONVERSATION_STORAGE_KEY, result.conversation_id)
    setMessages([{ role: 'user', content: greeting }, { role: 'assistant', content: result.response }])
    setProductCards(result.product_cards || [])
    await refreshCart(result.conversation_id)
    return result.conversation_id
  }

  async function sendMessage(text = chatInput) {
    const message = text.trim()
    if (!message || loading) return
    const clientId = `${Date.now()}-${Math.random().toString(36).slice(2)}`
    setError('')
    setLoading(true)
    setChatInput('')
    setMessages((current) => [...current, {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
      clientId,
      pending: true,
    }])
    try {
      const result = await apiRequest<{
        response: string
        conversation_id: string
        product_cards: ProductCard[]
        cart: Cart
        order?: ChatMessage['order']
      }>('/chat', {
        method: 'POST',
        body: JSON.stringify({ conversation_id: conversationId || null, message, language }),
      })
      setConversationId(result.conversation_id)
      window.localStorage.setItem(CONVERSATION_STORAGE_KEY, result.conversation_id)
      setMessages((current) => [
        ...current.map((item) => {
          if (item.clientId === clientId) return { ...item, pending: false }
          if (result.order && item.order?.id === result.order.id) return { ...item, order: result.order }
          return item
        }),
        { role: 'assistant', content: result.response, timestamp: new Date().toISOString(), order: result.order },
      ])
      setProductCards(result.product_cards || [])
      setCart(result.cart || {})
    } catch (cause) {
      setMessages((current) => current.map((item) => item.clientId === clientId ? { ...item, pending: false, failed: true } : item))
      setError(cause instanceof Error ? cause.message : 'Message could not be sent.')
    } finally {
      setLoading(false)
    }
  }

  function retryMessage(message: ChatMessage) {
    if (loading || !message.failed) return
    setMessages((current) => current.filter((item) => item.clientId !== message.clientId))
    void sendMessage(message.content)
  }

  async function startNewChat() {
    setBusyAction('new-chat')
    setError('')
    try {
      if (conversationId) await apiRequest(`/chat/${encodeURIComponent(conversationId)}`, { method: 'DELETE' })
      window.localStorage.removeItem(CONVERSATION_STORAGE_KEY)
      setConversationId('')
      setMessages([])
      setCart({})
      setProductCards([])
      setActiveView('chat')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not clear this conversation.')
    } finally {
      setBusyAction('')
    }
  }

  async function addToCart(productCard: ProductCard) {
    setError('')
    setBusyAction(productCard.id)
    try {
      const product = productById.get(productCard.id) || (await apiRequest<{ product: Product }>(`/products/${encodeURIComponent(productCard.id)}`)).product
      setAllProducts((current) => current.some((item) => item.id === product.id) ? current : [...current, product])
      const id = await ensureConversation()
      const result = await apiRequest<{ cart: Cart }>(`/cart/${encodeURIComponent(id)}/items`, {
        method: 'POST',
        body: JSON.stringify({ product_id: product.id, quantity: 1 }),
      })
      setCart(result.cart)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not add this item.')
    } finally {
      setBusyAction('')
    }
  }

  async function changeQuantity(productId: string, quantity: number) {
    if (!conversationId) return
    setError('')
    try {
      const result = quantity <= 0
        ? await apiRequest<{ cart: Cart }>(`/cart/${encodeURIComponent(conversationId)}/items/${encodeURIComponent(productId)}`, { method: 'DELETE' })
        : await apiRequest<{ cart: Cart }>(`/cart/${encodeURIComponent(conversationId)}/items/${encodeURIComponent(productId)}`, {
          method: 'PATCH',
          body: JSON.stringify({ quantity }),
        })
      setCart(result.cart)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not update your cart.')
    }
  }

  async function lookupOrder(id = orderIdInput) {
    const orderId = id.trim()
    if (!orderId) {
      setError('Enter an order ID to look it up.')
      return
    }
    setError('')
    setBusyAction('lookup')
    try {
      const [orderResponse, trackingResponse] = await Promise.all([
        apiRequest<{ order: Order }>(`/orders/${encodeURIComponent(orderId)}`),
        apiRequest<Record<string, any>>(`/orders/${encodeURIComponent(orderId)}/tracking`),
      ])
      setLatestOrder(orderResponse.order)
      setTracking(trackingResponse)
      setOrderIdInput(orderResponse.order.id)
      await refreshOrders()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not find this order.')
    } finally {
      setBusyAction('')
    }
  }

  function renderProductCard(product: ProductCard, compact = false) {
    return (
      <article className={`product-card${compact ? ' product-card-compact' : ''}`} key={product.id}>
        <button className="product-art" onClick={() => void openProduct(product.id)} aria-label={`View ${product.name} details`}>
          <span className={`product-illustration art-${product.category.replace(/[^a-z]/g, '-')}`} aria-hidden="true">
            {product.category === 'sunscreen' ? '☀' : product.category === 'serum' ? '◌' : product.category === 'cleanser' ? '◉' : '✿'}
          </span>
          <span className="demo-tag">DEMO</span>
        </button>
        <div className="product-card-body">
          <div className="product-category">{product.category}</div>
          <button className="product-name" onClick={() => void openProduct(product.id)}>{product.name}</button>
          {!compact && <p className="product-description">{product.description}</p>}
          {compact && product.benefits.length > 0 && <div className="card-benefits">{product.benefits.slice(0, 2).join(' · ')}</div>}
          <div className="product-bottom">
            <div className="price-stack">
              <strong>{money(product.price, currency)}</strong>
              {product.original_price && product.original_price > product.price && <del>{money(product.original_price, currency)}</del>}
            </div>
            <button className="button button-small button-dark" disabled={product.availability === 'out of stock' || product.stock_quantity === 0 || busyAction === product.id} onClick={() => void addToCart(product)}>
              {busyAction === product.id ? 'Adding…' : product.availability === 'out of stock' || product.stock_quantity === 0 ? 'Sold out' : 'Add'}
            </button>
          </div>
          {!compact && <div className="stock-hint">{product.stock_quantity ?? product.availability ?? 'Availability in catalog'} · Sample product data</div>}
        </div>
      </article>
    )
  }

  function renderOrderRow(order: Order) {
    const items = order.items?.map((item) => `${item.product_name} × ${item.quantity}`).join(', ') || 'Order items'
    return (
      <button className="order-history-row" key={order.id} onClick={() => void lookupOrder(order.id)}>
        <span className="order-history-main">
          <strong>{order.id}</strong>
          <small>{order.created_at ? `${new Date(order.created_at).toLocaleDateString()} · ` : ''}{items}</small>
        </span>
        <span className="order-history-state">
          <span className={`order-status status-${order.order_status}`}>{order.order_status.replaceAll('_', ' ')}</span>
          <small>Payment {order.payment_status}</small>
        </span>
        <strong className="order-history-total">{money(order.total, order.currency)}</strong>
      </button>
    )
  }

  return (
    <main className="app-shell" lang={language}>
      <aside className="sidebar">
        <a className="brand" href="#" onClick={(event) => { event.preventDefault(); setActiveView('chat') }}>
          <span className="brand-mark">tn</span>
          <span><strong>thai naturals</strong><small>SKINCARE STUDIO</small></span>
        </a>
        <div className="sidebar-label">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          <button className={activeView === 'chat' ? 'active' : ''} onClick={() => setActiveView('chat')}><span className="nav-icon">✳</span> {copy.navAssistant}</button>
          <button className={activeView === 'products' ? 'active' : ''} onClick={() => setActiveView('products')}><span className="nav-icon">▦</span> {copy.navProducts}</button>
          <button className={activeView === 'cart' ? 'active' : ''} onClick={() => setActiveView('cart')}><span className="nav-icon">♧</span> {copy.navCart} <span className="nav-count">{countInCart || ''}</span></button>
          <button className={activeView === 'orders' ? 'active' : ''} onClick={() => setActiveView('orders')}><span className="nav-icon">↗</span> {copy.navOrders}</button>
        </nav>
        <div className="sidebar-spacer" />
        <div className="sidebar-note">
          <span className={`status-dot status-${apiStatus}`} />
          <div><strong>Demo environment</strong><small>{apiStatus === 'online' ? 'API connected' : apiStatus === 'offline' ? 'API unavailable' : 'Connecting to API…'}</small></div>
        </div>
        <div className="sidebar-foot">Thai Naturals AI · Development preview</div>
      </aside>

      <section className="main-area">
        <header className="topbar">
          <div className="breadcrumb"><span>Thai Naturals</span><b>/</b><strong>{activeView === 'chat' ? copy.navAssistant : activeView === 'products' ? copy.navProducts : activeView === 'cart' ? copy.navCart : copy.navOrders}</strong></div>
          <div className="top-actions">
            <div className={`api-pill ${apiStatus}`}><span className="status-dot" />{apiStatus === 'online' ? 'API connected' : apiStatus === 'offline' ? 'API offline' : 'Checking API'}</div>
            <label className="language-control">
              <span>{copy.language}</span>
              <select value={language} onChange={(event) => setLanguage(event.target.value as Language)} aria-label={copy.language}>
                {LANGUAGES.map((option) => <option key={option.value} value={option.value}>{option.nativeName}</option>)}
              </select>
            </label>
            {activeView === 'chat' && <button className="button button-outline new-chat-button" onClick={() => void startNewChat()} disabled={busyAction === 'new-chat'}>＋ <span>{copy.newChat}</span></button>}
          </div>
        </header>

        {error && <div className="error-banner" role="alert"><span>{error}</span><button onClick={() => setError('')} aria-label="Dismiss error">×</button></div>}

        {activeView === 'chat' && (
          <div className="chat-layout">
            <section className="chat-main">
              <div className="chat-heading">
                <div className="eyebrow"><span className="sparkle">✳</span> {copy.eyebrow}</div>
                <h1>{copy.titleFirst}<br /><em>{copy.titleSecond}</em></h1>
                <p>{copy.intro}</p>
              </div>
              <div className="conversation">
                {messages.length === 0 ? (
                  <div className="welcome-card">
                    <div className="assistant-avatar">tn</div>
                    <div className="welcome-copy">
                      <div className="message-meta">{copy.assistant} <span>JUST NOW</span></div>
                      <p>{copy.welcome}</p>
                    </div>
                  </div>
                ) : messages.map((message, index) => (
                  <div className={`message-row ${message.role}`} key={`${message.timestamp || index}-${index}`}>
                    {message.role === 'assistant' && <div className="assistant-avatar">tn</div>}
                    <div className="message-content">
                      <div className="message-meta">{message.role === 'assistant' ? copy.assistant : 'YOU'} <span>{message.pending ? copy.sending : message.failed ? copy.failed : shortDate(message.timestamp)}</span></div>
                      <p>{renderMessageContent(message.content)}</p>
                      {message.role === 'assistant' && message.order && message.order.payment_status !== 'paid' && (
                        <button
                          className="payment-verify-chat"
                          onClick={() => void sendMessage(`I have completed the demo payment for order ${message.order?.id}. Please verify the payment status.`)}
                          disabled={loading}
                        >
                          I’ve paid — verify my order
                        </button>
                      )}
                      {message.failed && <button className="retry-message" onClick={() => retryMessage(message)} disabled={loading}>{copy.retry}</button>}
                    </div>
                    {message.role === 'user' && <div className="user-avatar">Y</div>}
                  </div>
                ))}
                {loading && <div className="message-row"><div className="assistant-avatar">tn</div><div className="message-content"><div className="message-meta">{copy.assistant}</div><p className="typing"><i /><i /><i /> <span>{copy.typing}</span></p></div></div>}
                {productCards.length > 0 && (
                  <div className="chat-recommendations">
                    <div className="recommendation-label">{copy.recommendations}</div>
                    <div className="recommendation-grid">{productCards.map((card) => renderProductCard(card, true))}</div>
                  </div>
                )}
                <div ref={messageEndRef} />
              </div>
              <div className="composer-wrap">
                {messages.length === 0 && <div className="suggestion-row">
                  {copy.suggestions.map((suggestion) => <button key={suggestion} onClick={() => void sendMessage(suggestion)}>{suggestion} <span>↗</span></button>)}
                </div>}
                <form className="composer" onSubmit={(event) => { event.preventDefault(); void sendMessage() }}>
                  <input value={chatInput} onChange={(event) => setChatInput(event.target.value)} placeholder={copy.placeholder} aria-label={copy.placeholder} />
                  <button type="submit" disabled={!chatInput.trim() || loading} aria-label={copy.send}>↑</button>
                </form>
                <div className="composer-disclaimer">{copy.disclaimer}</div>
              </div>
            </section>
            <aside className="chat-rail">
              <div className="rail-card rail-intro">
                <div className="rail-art">✳</div>
                <span className="eyebrow">THOUGHTFULLY MADE</span>
                <h3>Care that feels<br />like coming home.</h3>
                <p>Explore gentle, ingredient-conscious skincare inspired by nature.</p>
                <button className="text-link" onClick={() => setActiveView('products')}>Explore our products <span>↗</span></button>
              </div>
              <div className="rail-card privacy-card"><div className="privacy-icon">⌑</div><strong>Your demo, your data</strong><p>Chats and carts live in temporary memory and clear when the API restarts.</p></div>
              <button className="rail-cart-button" onClick={() => setActiveView('cart')}><span>♧</span><div><strong>Your bag</strong><small>{countInCart ? `${countInCart} item${countInCart === 1 ? '' : 's'} added` : 'Ready when you are'}</small></div><b>→</b></button>
            </aside>
          </div>
        )}

        {activeView === 'products' && (
          <section className="view-content">
            <div className="section-heading">
              <div><div className="eyebrow">THE THAI NATURALS EDIT</div><h1>Find your <em>feel-good.</em></h1><p>Explore our demo catalog. Product information and stock are sample data.</p></div>
              <span className="catalog-count">{products.length} DEMO PRODUCTS</span>
            </div>
            <div className="catalog-toolbar">
              <label className="search-field"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void refreshProducts(query, category, skinType, concern, maxPrice) }} placeholder="Search products, ingredients, concerns…" /><button onClick={() => void refreshProducts(query, category, skinType, concern, maxPrice)}>Search</button></label>
              <div className="catalog-filters">
                <select value={category} onChange={(event) => { setCategory(event.target.value); void refreshProducts(query, event.target.value, skinType, concern, maxPrice) }} aria-label="Filter by category">
                  <option value="">All categories</option>
                  {[...new Set(allProducts.map((product) => product.category))].sort().map((item) => <option key={item} value={item}>{item[0].toUpperCase() + item.slice(1)}</option>)}
                </select>
                <select value={skinType} onChange={(event) => { setSkinType(event.target.value); void refreshProducts(query, category, event.target.value, concern, maxPrice) }} aria-label="Filter by skin type">
                  <option value="">All skin types</option>
                  {[...new Set(allProducts.flatMap((product) => product.skin_types))].sort().map((item) => <option key={item} value={item}>{item[0].toUpperCase() + item.slice(1)}</option>)}
                </select>
                <select value={concern} onChange={(event) => { setConcern(event.target.value); void refreshProducts(query, category, skinType, event.target.value, maxPrice) }} aria-label="Filter by skin concern">
                  <option value="">All concerns</option>
                  {[...new Set(allProducts.flatMap((product) => product.concerns))].sort().map((item) => <option key={item} value={item}>{item[0].toUpperCase() + item.slice(1)}</option>)}
                </select>
                <input className="max-price-filter" type="number" min="1" value={maxPrice} onChange={(event) => setMaxPrice(event.target.value)} onBlur={() => void refreshProducts(query, category, skinType, concern, maxPrice)} onKeyDown={(event) => { if (event.key === 'Enter') void refreshProducts(query, category, skinType, concern, maxPrice) }} placeholder="Max ₹" aria-label="Maximum price" />
              </div>
            </div>
            {catalogLoading ? <div className="loading-state">Loading the catalog…</div> : products.length ? <div className="catalog-grid">{products.map((product) => renderProductCard(product))}</div> : <div className="empty-state"><span>⌕</span><h3>No products found</h3><p>Try another search or clear the category filter.</p><button className="button button-outline" onClick={() => { setQuery(''); setCategory(''); setSkinType(''); setConcern(''); setMaxPrice(''); void refreshProducts() }}>Clear filters</button></div>}
          </section>
        )}

        {activeView === 'cart' && (
          <section className="view-content">
            <div className="section-heading">
              <div><div className="eyebrow">A LITTLE SOMETHING FOR YOU</div><h1>Your <em>shopping bag.</em></h1><p>Review your picks before checkout.</p></div>
              <button className="text-link" onClick={() => setActiveView('products')}>Continue shopping <span>↗</span></button>
            </div>
            {!cartItems.length ? <div className="empty-state"><span>♧</span><h3>Your bag is taking a breather</h3><p>Explore the catalog and add a few things to get started.</p><button className="button button-dark" onClick={() => setActiveView('products')}>Browse products <span>→</span></button></div> : (
              <div className="cart-layout">
                <div className="cart-list">
                  {cartItems.map(({ product, quantity }) => <div className="cart-row" key={product.id}>
                    <div className="cart-thumb"><span>{product.category === 'sunscreen' ? '☀' : '✿'}</span></div>
                    <div className="cart-product"><span className="product-category">{product.category}</span><strong>{product.name}</strong><small>{money(product.price)} each</small></div>
                    <div className="quantity-controls"><button onClick={() => void changeQuantity(product.id, quantity - 1)} aria-label={`Remove one ${product.name}`}>−</button><span>{quantity}</span><button onClick={() => void changeQuantity(product.id, quantity + 1)} aria-label={`Add one ${product.name}`}>＋</button></div>
                    <strong className="line-total">{money(product.price * quantity)}</strong>
                    <button className="remove-item" onClick={() => void changeQuantity(product.id, 0)} aria-label={`Remove ${product.name}`}>×</button>
                  </div>)}
                </div>
                <div className="order-summary">
                  <div className="summary-title">ORDER SUMMARY</div>
                  {cartItems.map(({ product, quantity }) => <div className="summary-line" key={product.id}><span>{product.name} <small>× {quantity}</small></span><strong>{money(product.price * quantity)}</strong></div>)}
                  <div className="summary-divider" />
                  <p className="demo-note">Ready to check out? Tell the assistant “I’d like to place my order” and it will collect delivery details, confirm the total, and create your payment link.</p>
                  <button className="button button-dark full-button" onClick={() => setActiveView('chat')}>Checkout with the assistant</button>
                </div>
              </div>
            )}
          </section>
        )}

        {activeView === 'orders' && (
          <section className="view-content">
            <div className="section-heading">
              <div><div className="eyebrow">HERE WHEN YOU NEED US</div><h1>Orders & <em>tracking.</em></h1><p>Active orders, payment status, and your order history.</p></div>
            </div>
            <div className="order-history-section">
              <div className="order-history-heading"><h2>Active orders</h2><button className="text-link" onClick={() => void refreshOrders()}>Refresh ↻</button></div>
              {activeOrders.length ? <div className="order-history-list">{activeOrders.map(renderOrderRow)}</div> : <p className="order-history-empty">No active orders yet. Start a checkout in the assistant chat.</p>}
            </div>
            <div className="order-history-section">
              <div className="order-history-heading"><h2>Order history</h2><span>{orderHistory.length} orders</span></div>
              {orderHistory.length ? <div className="order-history-list">{orderHistory.map(renderOrderRow)}</div> : <p className="order-history-empty">Completed and pending orders will appear here.</p>}
            </div>
            <div className="order-lookup">
              <span>⌕</span><input value={orderIdInput} onChange={(event) => setOrderIdInput(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void lookupOrder() }} placeholder="Enter your order ID, e.g. TN-AB12CD34" />
              <button className="button button-dark" onClick={() => void lookupOrder()} disabled={busyAction === 'lookup'}>{busyAction === 'lookup' ? 'Looking…' : 'Find order'}</button>
            </div>
            {latestOrder ? <div className="order-detail">
              <div className="order-topline"><div><div className="eyebrow">DEMO ORDER</div><h2>{latestOrder.id}</h2></div><span className={`order-status status-${latestOrder.order_status}`}>{latestOrder.order_status.replaceAll('_', ' ')}</span></div>
              <div className="order-item-list">{latestOrder.items?.map((item) => <div className="summary-line" key={item.product_id}><span>{item.product_name} <small>× {item.quantity}</small></span><strong>{money(item.line_total)}</strong></div>)}</div>
              <div className="order-total"><span>Total</span><strong>{money(latestOrder.total, latestOrder.currency)}</strong></div>
              <div className="payment-state"><span className={latestOrder.payment_status === 'paid' ? 'payment-check' : 'payment-pending'}>{latestOrder.payment_status === 'paid' ? '✓' : '○'}</span><div><strong>Demo payment {latestOrder.payment_status}</strong><small>This is a simulation, not a real transaction.</small></div></div>
              {latestOrder.payment_url && latestOrder.payment_status !== 'paid' && <div className="order-actions"><a className="button button-outline" href={latestOrder.payment_url} target="_blank" rel="noreferrer">Open demo payment page ↗</a><button className="button button-dark" onClick={() => void lookupOrder(latestOrder.id)} disabled={busyAction === 'lookup'}>{busyAction === 'lookup' ? 'Checking…' : 'Check payment status'}</button></div>}
              {(tracking?.tracking_number || latestOrder.tracking_number) && <div className="tracking-box"><span className="tracking-icon">↗</span><div><strong>Demo tracking</strong><small>{tracking?.tracking_number || latestOrder.tracking_number}</small></div>{(tracking?.tracking_url || latestOrder.tracking_url) && <a href={tracking?.tracking_url || latestOrder.tracking_url} target="_blank" rel="noreferrer">View ↗</a>}</div>}
              {latestOrder.payment_status === 'paid' && !tracking && <button className="text-link" onClick={() => void lookupOrder(latestOrder.id)}>Refresh tracking details ↻</button>}
            </div> : <div className="empty-state order-empty"><span>↗</span><h3>No order selected</h3><p>Select an order above or enter an order ID to view its details.</p></div>}
            <div className="demo-caveat"><strong>About this demo</strong><p>Orders, payments, and tracking are simulated. The API uses in-memory storage, so data is cleared when the backend restarts.</p></div>
          </section>
        )}
      </section>

      {selectedProduct && <div className="modal-backdrop" onClick={() => setSelectedProduct(null)} role="presentation">
        <section className="product-modal" role="dialog" aria-modal="true" aria-labelledby="modal-title" onClick={(event) => event.stopPropagation()}>
          <button className="modal-close" onClick={() => setSelectedProduct(null)} aria-label="Close product details">×</button>
          <div className="modal-art"><span>{selectedProduct.category === 'sunscreen' ? '☀' : '✿'}</span><span className="demo-tag">DEMO PRODUCT</span></div>
          <div className="modal-copy"><div className="product-category">{selectedProduct.category}</div><h2 id="modal-title">{selectedProduct.name}</h2><p>{selectedProduct.description}</p>
            <div className="modal-price">{money(selectedProduct.price)} <del>{money(selectedProduct.original_price)}</del></div>
            <div className="detail-list"><div><strong>INGREDIENTS</strong><span>{selectedProduct.ingredients.join(' · ')}</span></div><div><strong>BENEFITS</strong><span>{selectedProduct.benefits.join(' · ')}</span></div><div><strong>SKIN TYPES</strong><span>{selectedProduct.skin_types.join(' · ')}</span></div><div><strong>HOW TO USE</strong><span>{selectedProduct.how_to_use}</span></div><div><strong>PRECAUTIONS</strong><span>{selectedProduct.precautions}</span></div></div>
            <button className="button button-dark full-button" onClick={() => { void addToCart(selectedProduct); setSelectedProduct(null) }}>Add to bag · {money(selectedProduct.price)}</button>
          </div>
        </section>
      </div>}
    </main>
  )
}
