// components/common/buttonStyles.js — M69: 버튼 스타일 공통 모듈
// 스마트팩토리 블루 파스텔 버튼 스타일

const base = 'rounded-2xl border-2 px-4 py-3 text-sm font-extrabold text-sf-brown transition active:translate-y-[1px] disabled:opacity-60 disabled:cursor-not-allowed';

const variants = {
  primary: 'border-blue-300/50 bg-gradient-to-r from-blue-100 to-blue-50 shadow-md hover:from-blue-200 hover:to-blue-100 hover:border-blue-400/50',
  secondary: 'border-blue-200/50 bg-blue-50 shadow-sm hover:bg-blue-100',
};

const layouts = {
  block: 'w-full',
  inline: 'inline-flex items-center justify-center gap-2 whitespace-nowrap',
};

export function sfButton(variant = 'primary', layout = 'block') {
  return `${base} ${variants[variant] || variants.primary} ${layouts[layout] || layouts.block}`;
}

// 편의 상수
export const sfBtn = sfButton('primary', 'block');
export const sfBtnSecondary = sfButton('secondary', 'block');
export const sfBtnInline = sfButton('primary', 'inline');
export const sfBtnSecondaryInline = sfButton('secondary', 'inline');
