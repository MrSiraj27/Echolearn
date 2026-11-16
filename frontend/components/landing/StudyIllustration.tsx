"use client";

import { motion } from "framer-motion";

// Line-art study scene for the landing page: books, an open notebook, a laptop, a plant and an
// idea bulb, drawn in ink on cream so it follows the light/dark theme through currentColor.
export function StudyIllustration({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 520 380" className={className} role="img" aria-label="Study desk with books, a laptop and an idea">
      <defs>
        <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="6" stroke="currentColor" strokeWidth="1" opacity="0.35" />
        </pattern>
      </defs>

      {/* soft backdrop */}
      <circle cx="180" cy="190" r="150" className="fill-neutral-200/70 dark:fill-neutral-800/60" />

      <g fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
        {/* desk line */}
        <path d="M18 330 H500" />

        {/* plant */}
        <path d="M70 330 V286 H118 V330" className="fill-neutral-50 dark:fill-neutral-900" />
        <path d="M66 286 H122" />
        <motion.g
          style={{ originX: 0.5, originY: 1 }}
          animate={{ rotate: [0, 2.5, -1.5, 0] }}
          transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
        >
        <path d="M94 286 C92 250 90 220 96 182" />
        <path d="M95 236 C70 226 52 206 50 178 C76 184 92 204 95 236 Z" className="fill-neutral-900 dark:fill-neutral-200" />
        <path d="M96 214 C118 198 136 174 136 146 C112 156 98 182 96 214 Z" className="fill-neutral-900 dark:fill-neutral-200" />
        <path d="M95 262 C116 256 134 240 140 218 C118 222 100 238 95 262 Z" className="fill-neutral-50 dark:fill-neutral-900" />
        <path d="M94 258 C72 254 56 240 48 222 C70 222 88 236 94 258 Z" className="fill-neutral-50 dark:fill-neutral-900" />
        </motion.g>

        {/* stacked books */}
        <rect x="150" y="306" width="150" height="24" rx="4" className="fill-neutral-900 dark:fill-neutral-200" />
        <rect x="160" y="284" width="132" height="22" rx="4" className="fill-neutral-50 dark:fill-neutral-900" />
        <path d="M172 295 H280" strokeWidth="2" />

        {/* open book on the stack */}
        <path d="M226 284 C204 268 176 262 148 266 L156 196 C184 192 208 198 226 214 Z" className="fill-neutral-50 dark:fill-neutral-900" />
        <path d="M226 284 C248 268 276 262 304 266 L296 196 C268 192 244 198 226 214 Z" className="fill-neutral-50 dark:fill-neutral-900" />
        <path d="M226 214 V284" />
        <g strokeWidth="2" opacity="0.7">
          <path d="M166 214 C184 212 200 216 214 224" />
          <path d="M164 232 C182 230 198 234 212 242" />
          <path d="M162 250 C180 248 196 252 210 260" />
          <path d="M240 224 C254 216 270 212 288 214" />
          <path d="M242 242 C256 234 272 230 290 232" />
        </g>

        {/* laptop */}
        <path d="M330 330 L352 222 H478 L462 330" className="fill-neutral-900 dark:fill-neutral-200" />
        <path d="M312 330 H486" strokeWidth="5" />
        <circle cx="412" cy="276" r="5" className="fill-neutral-50 dark:fill-neutral-900" stroke="none" />

        {/* idea bulb */}
        <g transform="translate(372 64)">
          <motion.circle
            cx="34" cy="40" r="46" stroke="none" className="fill-neutral-300/60 dark:fill-neutral-600/40"
            animate={{ opacity: [0.2, 0.9, 0.2], scale: [0.9, 1.05, 0.9] }}
            style={{ originX: 0.5, originY: 0.5 }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
          />
          <path d="M0 40 C0 18 16 4 34 4 C52 4 68 18 68 40 C68 56 58 64 52 74 V86 H16 V74 C10 64 0 56 0 40 Z" className="fill-neutral-50 dark:fill-neutral-900" />
          <path d="M18 94 H50 M22 102 H46" />
          <path d="M26 74 L30 46 L34 58 L38 46 L42 74" strokeWidth="2.5" />
          <motion.g
            strokeWidth="2.5"
            animate={{ opacity: [0.35, 1, 0.35] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
          >
            <path d="M34 -18 V-6" />
            <path d="M-14 6 L-4 14" />
            <path d="M82 6 L72 14" />
            <path d="M-24 40 H-12" />
            <path d="M80 40 H92" />
          </motion.g>
        </g>

        {/* thought trail from book to idea */}
        <motion.path
          d="M300 186 C336 150 330 112 360 110"
          strokeWidth="2"
          strokeDasharray="2 9"
          animate={{ strokeDashoffset: [0, -22] }}
          transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
        />
        <path d="M462 120 C500 140 506 196 470 214" strokeWidth="2" />
      </g>

      <rect x="150" y="306" width="150" height="24" rx="4" fill="url(#hatch)" className="text-neutral-50 dark:text-neutral-900" />
    </svg>
  );
}
