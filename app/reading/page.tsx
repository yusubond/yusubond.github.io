import { genPageMetadata } from 'app/seo'

export const metadata = genPageMetadata({ title: '阅读' })

export default function Reading() {
  return (
    <>
      <div className="divide-y divide-gray-200 dark:divide-gray-700">
        <div className="space-y-2 pt-6 pb-8 md:space-y-5">
          <h1 className="text-3xl leading-9 font-extrabold tracking-tight text-gray-900 sm:text-4xl sm:leading-10 md:text-6xl md:leading-14 dark:text-gray-100">
            阅读书单
          </h1>
          <p className="text-lg leading-7 text-gray-500 dark:text-gray-400">
            我读过的书，不定期更新
          </p>
        </div>
        <div className="py-12">
          <p className="text-lg leading-7 text-gray-500 dark:text-gray-400">
            <a
              href="https://github.com/yusubond/reading"
              className="text-primary-500 hover:text-primary-600 dark:hover:text-primary-400"
              target="_blank"
              rel="noopener noreferrer"
            >
              我的阅读书单 →
            </a>
          </p>
        </div>
      </div>
    </>
  )
}
