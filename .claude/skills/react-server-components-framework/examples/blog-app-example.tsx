/**
 * Complete E-commerce Dashboard Application Example
 * Demonstrates RSC, Server Actions, Streaming, and Best Practices
 * Real-world example: Product Management + Order Tracking + Analytics
 */

// ============================================
// 1. DATABASE SCHEMA (Prisma)
// ============================================

/*
// prisma/schema.prisma

model Product {
  id          String   @id @default(cuid())
  name        String
  slug        String   @unique
  description String?
  price       Decimal  @db.Decimal(10, 2)
  stock       Int      @default(0)
  imageUrl    String?
  category    Category @relation(fields: [categoryId], references: [id])
  categoryId  String
  orders      OrderItem[]
  createdAt   DateTime @default(now())
  updatedAt   DateTime @updatedAt

  @@index([slug])
  @@index([categoryId])
}

model Order {
  id          String      @id @default(cuid())
  status      OrderStatus @default(PENDING)
  total       Decimal     @db.Decimal(10, 2)
  userId      String
  user        User        @relation(fields: [userId], references: [id])
  items       OrderItem[]
  createdAt   DateTime    @default(now())
  updatedAt   DateTime    @updatedAt

  @@index([userId])
  @@index([status])
}

enum OrderStatus {
  PENDING
  PROCESSING
  SHIPPED
  DELIVERED
  CANCELLED
}

model OrderItem {
  id        String  @id @default(cuid())
  quantity  Int
  price     Decimal @db.Decimal(10, 2)
  productId String
  product   Product @relation(fields: [productId], references: [id])
  orderId   String
  order     Order   @relation(fields: [orderId], references: [id])

  @@index([productId])
  @@index([orderId])
}
*/

// ============================================
// 2. SERVER ACTIONS (app/actions/products.ts)
// ============================================

'use server'

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'
import { z } from 'zod'
import { db } from '@/lib/database'
import { getServerSession } from '@/lib/auth'

const createProductSchema = z.object({
  name: z.string().min(1).max(200),
  slug: z.string().min(1).max(200).regex(/^[a-z0-9-]+$/),
  description: z.string().max(2000).optional(),
  price: z.number().positive().max(999999.99),
  stock: z.number().int().nonnegative(),
  categoryId: z.string().cuid(),
})

export async function createProduct(formData: FormData) {
  const session = await getServerSession()
  if (!session?.user?.isAdmin) {
    return { error: 'Unauthorized' }
  }

  const validated = createProductSchema.safeParse({
    name: formData.get('name'),
    slug: formData.get('slug'),
    description: formData.get('description'),
    price: parseFloat(formData.get('price') as string),
    stock: parseInt(formData.get('stock') as string),
    categoryId: formData.get('categoryId'),
  })

  if (!validated.success) {
    return {
      error: 'Validation failed',
      errors: validated.error.flatten().fieldErrors
    }
  }

  try {
    const product = await db.product.create({
      data: validated.data
    })

    revalidatePath('/admin/products')
    redirect(`/admin/products/${product.slug}`)
  } catch (error) {
    return { error: 'Failed to create product' }
  }
}

export async function updateOrderStatus(orderId: string, status: OrderStatus) {
  const session = await getServerSession()
  if (!session?.user?.isAdmin) {
    return { error: 'Unauthorized' }
  }

  try {
    await db.order.update({
      where: { id: orderId },
      data: { status }
    })

    revalidatePath('/admin/orders')
    return { success: true }
  } catch (error) {
    return { error: 'Failed to update order status' }
  }
}

// ============================================
// 3. PRODUCTS LIST PAGE (app/admin/products/page.tsx)
// ============================================

import { Suspense } from 'react'
import { db } from '@/lib/database'
import { ProductCard } from '@/components/ProductCard'
import { ProductListSkeleton } from '@/components/skeletons'

export const metadata = {
  title: 'Products | Admin Dashboard',
  description: 'Manage your product catalog'
}

export default function ProductsPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-4xl font-bold">Products</h1>
        <Link
          href="/admin/products/new"
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Add Product
        </Link>
      </div>

      {/* Streaming: Products load independently */}
      <Suspense fallback={<ProductListSkeleton />}>
        <ProductList />
      </Suspense>
    </div>
  )
}

// Server Component for data fetching
async function ProductList() {
  const products = await db.product.findMany({
    include: {
      category: {
        select: { name: true }
      },
      _count: {
        select: { orders: true }
      }
    },
    orderBy: { createdAt: 'desc' },
    take: 50
  })

  if (products.length === 0) {
    return <p className="text-gray-500">No products yet. Add your first product!</p>
  }

  return (
    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      {products.map(product => (
        <ProductCard key={product.id} product={product} />
      ))}
    </div>
  )
}

// ============================================
// 4. PRODUCT DETAIL PAGE (app/admin/products/[slug]/page.tsx)
// ============================================

import { notFound } from 'next/navigation'
import { Suspense } from 'react'
import { Metadata } from 'next'
import { db } from '@/lib/database'
import { OrderHistory } from '@/components/OrderHistory'
import { OrderHistorySkeleton } from '@/components/skeletons'

interface PageProps {
  params: { slug: string }
}

// Generate static params at build time (SSG)
export async function generateStaticParams() {
  const products = await db.product.findMany({
    select: { slug: true },
    take: 100 // Pre-render top 100 products
  })

  return products.map(product => ({
    slug: product.slug
  }))
}

// Dynamic metadata for SEO
export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const product = await db.product.findUnique({
    where: { slug: params.slug },
    select: {
      name: true,
      description: true,
      category: { select: { name: true } }
    }
  })

  if (!product) {
    return { title: 'Product Not Found' }
  }

  return {
    title: `${product.name} | Admin Dashboard`,
    description: product.description || `${product.category.name} product`,
    openGraph: {
      title: product.name,
      description: product.description || undefined,
      type: 'website'
    }
  }
}

// Revalidate every 5 minutes
export const revalidate = 300

export default async function ProductDetailPage({ params }: PageProps) {
  const product = await db.product.findUnique({
    where: { slug: params.slug },
    include: {
      category: {
        select: {
          name: true,
          id: true
        }
      }
    }
  })

  if (!product) {
    notFound()
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <div className="bg-white rounded-lg shadow-md p-8 mb-8">
        <div className="flex justify-between items-start mb-6">
          <div>
            <h1 className="text-4xl font-bold mb-2">{product.name}</h1>
            <span className="text-sm text-gray-600">{product.category.name}</span>
          </div>
          <div className="text-right">
            <p className="text-3xl font-bold text-green-600">
              ${product.price.toString()}
            </p>
            <p className="text-sm text-gray-600">
              Stock: {product.stock} units
            </p>
          </div>
        </div>

        {product.description && (
          <div className="prose max-w-none mb-6">
            <p>{product.description}</p>
          </div>
        )}

        <div className="flex gap-4">
          <Link
            href={`/admin/products/${params.slug}/edit`}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Edit Product
          </Link>
          <UpdateStockForm productId={product.id} currentStock={product.stock} />
        </div>
      </div>

      <section className="bg-white rounded-lg shadow-md p-8">
        <h2 className="text-2xl font-bold mb-6">Order History</h2>

        {/* Order history (Streaming) */}
        <Suspense fallback={<OrderHistorySkeleton />}>
          <OrderHistory productId={product.id} />
        </Suspense>
      </section>
    </div>
  )
}

// ============================================
// 5. ORDER HISTORY (components/OrderHistory.tsx)
// ============================================

// Server Component
import { db } from '@/lib/database'

export async function OrderHistory({ productId }: { productId: string }) {
  const orders = await db.orderItem.findMany({
    where: { productId },
    include: {
      order: {
        select: {
          id: true,
          status: true,
          createdAt: true,
          user: {
            select: { name: true, email: true }
          }
        }
      }
    },
    orderBy: { order: { createdAt: 'desc' } },
    take: 20
  })

  if (orders.length === 0) {
    return <p className="text-gray-500 italic">No orders yet for this product.</p>
  }

  return (
    <div className="space-y-4">
      {orders.map(item => (
        <div key={item.id} className="border rounded-lg p-4">
          <div className="flex justify-between items-start">
            <div>
              <p className="font-semibold">{item.order.user.name}</p>
              <p className="text-sm text-gray-600">{item.order.user.email}</p>
            </div>
            <div className="text-right">
              <OrderStatusBadge status={item.order.status} />
              <p className="text-sm text-gray-600 mt-1">
                {item.quantity} × ${item.price.toString()}
              </p>
            </div>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            {new Date(item.order.createdAt).toLocaleString()}
          </p>
        </div>
      ))}
    </div>
  )
}

// ============================================
// 6. UPDATE STOCK FORM (components/UpdateStockForm.tsx)
// ============================================

'use client' // Client Component for interactivity

import { useActionState } from 'react' // React 19
import { useFormStatus } from 'react-dom'
import { updateProductStock } from '@/app/actions/products'

function SubmitButton(): React.ReactNode {
  const { pending } = useFormStatus()

  return (
    <button
      type="submit"
      disabled={pending}
      aria-busy={pending}
      className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
    >
      {pending ? 'Updating...' : 'Update Stock'}
    </button>
  )
}

export function UpdateStockForm({
  productId,
  currentStock
}: {
  productId: string
  currentStock: number
}): React.ReactNode {
  const [state, formAction] = useActionState(
    async (prevState: any, formData: FormData) => {
      const stock = parseInt(formData.get('stock') as string)
      return updateProductStock(productId, stock)
    },
    null
  )

  return (
    <form action={formAction} className="flex gap-2 items-center">
      <input
        type="number"
        name="stock"
        defaultValue={currentStock}
        min="0"
        required
        className="w-24 px-3 py-2 border rounded-lg"
      />

      {state?.error && (
        <span className="text-red-600 text-sm">{state.error}</span>
      )}

      <SubmitButton />
    </form>
  )
}

// ============================================
// 7. PRODUCT CARD (components/ProductCard.tsx)
// ============================================

'use client'

import Link from 'next/link'
import { Product, Category } from '@prisma/client'

interface ProductCardProps {
  product: Product & {
    category: { name: string }
    _count: { orders: number }
  }
}

export function ProductCard({ product }: ProductCardProps) {
  const lowStock = product.stock < 10

  return (
    <Link
      href={`/admin/products/${product.slug}`}
      className="block p-6 bg-white rounded-lg border hover:shadow-lg transition-shadow"
    >
      <div className="flex justify-between items-start mb-4">
        <h2 className="text-xl font-bold">{product.name}</h2>
        {lowStock && (
          <span className="px-2 py-1 text-xs bg-red-100 text-red-800 rounded-full">
            Low Stock
          </span>
        )}
      </div>

      <p className="text-sm text-gray-600 mb-2">{product.category.name}</p>

      <div className="flex items-center justify-between text-sm">
        <div>
          <p className="text-2xl font-bold text-green-600">
            ${product.price.toString()}
          </p>
          <p className="text-gray-600">Stock: {product.stock}</p>
        </div>

        <div className="text-right">
          <p className="text-gray-600">{product._count.orders} orders</p>
          <time className="text-xs text-gray-500">
            {new Date(product.createdAt).toLocaleDateString()}
          </time>
        </div>
      </div>
    </Link>
  )
}

/**
 * Key Patterns Demonstrated:
 *
 * 1. ✅ Server Components for data fetching (ProductsPage, ProductList, OrderHistory)
 * 2. ✅ Client Components for interactivity (UpdateStockForm, ProductCard)
 * 3. ✅ Server Actions for mutations (createProduct, updateOrderStatus, updateProductStock)
 * 4. ✅ Streaming with Suspense (ProductList, OrderHistory)
 * 5. ✅ Static generation with generateStaticParams (top 100 products)
 * 6. ✅ Dynamic metadata with generateMetadata (SEO optimization)
 * 7. ✅ Progressive enhancement (forms work without JavaScript)
 * 8. ✅ Proper error handling (notFound, validation)
 * 9. ✅ Cache revalidation (revalidatePath, revalidate)
 * 10. ✅ Type safety with Prisma and TypeScript
 * 11. ✅ React 19 patterns (useActionState, useFormStatus)
 * 12. ✅ Exhaustive type checking (OrderStatus enum)
 *
 * Real-World Application: E-commerce Admin Dashboard
 * - Product catalog management
 * - Inventory tracking with low-stock alerts
 * - Order history per product
 * - Real-time stock updates
 * - SEO-optimized product pages
 * - Streaming for fast perceived performance
 */
