import { createRouter, createWebHistory, RouterView } from 'vue-router'
import { h } from 'vue'
import i18n from '../i18n'
import Home from '../views/Home.vue'
import Predict from '../views/Predict.vue'
import Prediction from '../views/Prediction.vue'
import Training from '../views/Training.vue'
import About from '../views/About.vue'
import Privacy from '../views/Privacy.vue'
import HowItWorks from '../views/HowItWorks.vue'
import AuthSuccess from '../views/AuthSuccess.vue'
import AuthError from '../views/AuthError.vue'

const routes = [
  {
    path: '/:lang(en|it)?',
    component: { render: () => h(RouterView) },
    children: [
      {
        path: '',
        name: 'Home',
        component: Home
      },
      {
        path: 'predict',
        name: 'Predict',
        component: Predict
      },
      {
        path: 'analysis/:gpxId',
        name: 'Analysis',
        redirect: to => {
          const lang = to.params.lang || 'en'
          // If lang is implicit (empty), we might want to redirect to /prediction or /en/prediction
          // Let's keep it simple: keep the current lang context or default to nothing if it was nothing
          const prefix = to.params.lang ? `/${to.params.lang}` : ''
          return `${prefix}/prediction/${to.params.gpxId}`
        }
      },
      {
        path: 'prediction/:gpxId',
        name: 'Prediction',
        component: Prediction,
        props: true
      },
      {
        path: 'training',
        name: 'Training',
        component: Training
      },
      {
        path: 'chi-sono',
        name: 'AboutIt',
        component: About
      },
      {
        path: 'who-i-am',
        name: 'AboutEn',
        component: About
      },
      {
        path: 'privacy',
        name: 'Privacy',
        component: Privacy
      },
      {
        path: 'how-it-works',
        name: 'HowItWorksEn',
        component: HowItWorks
      },
      {
        path: 'come-funziona',
        name: 'HowItWorksIt',
        component: HowItWorks
      },
      {
        path: 'auth-success',
        name: 'AuthSuccess',
        component: AuthSuccess
      },
      {
        path: 'auth-error',
        name: 'AuthError',
        component: AuthError
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  }
})

const supportedLangs = ['en', 'it']
const getStoredLang = () => {
  if (typeof localStorage === 'undefined') return null
  return localStorage.getItem('preferred_lang')
}

const setStoredLang = (lang) => {
  if (typeof localStorage === 'undefined') return
  localStorage.setItem('preferred_lang', lang)
}

const getBrowserLang = () => {
  if (typeof navigator === 'undefined') return null
  const navLang = navigator.language || (navigator.languages && navigator.languages[0])
  if (!navLang) return null
  const short = navLang.toLowerCase().split('-')[0]
  return supportedLangs.includes(short) ? short : null
}

router.beforeEach((to, from, next) => {
  const lang = to.params.lang
  if (lang && supportedLangs.includes(lang)) {
    i18n.global.locale.value = lang
    setStoredLang(lang)
  } else {
    // If no lang param, use stored or browser language without forcing URL change
    const stored = getStoredLang()
    const fallback = (stored && supportedLangs.includes(stored)) ? stored : (getBrowserLang() || 'en')
    i18n.global.locale.value = fallback
    setStoredLang(fallback)
  }
  next()
})

export default router
