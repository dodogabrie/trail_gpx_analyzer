import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Prediction from '../views/Prediction.vue'
import Training from '../views/Training.vue'
import AuthSuccess from '../views/AuthSuccess.vue'
import AuthError from '../views/AuthError.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/analysis/:gpxId',
    name: 'Analysis',
    redirect: to => `/prediction/${to.params.gpxId}`
  },
  {
    path: '/prediction/:gpxId',
    name: 'Prediction',
    component: Prediction,
    props: true
  },
  {
    path: '/training',
    name: 'Training',
    component: Training
  },
  {
    path: '/auth-success',
    name: 'AuthSuccess',
    component: AuthSuccess
  },
  {
    path: '/auth-error',
    name: 'AuthError',
    component: AuthError
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
