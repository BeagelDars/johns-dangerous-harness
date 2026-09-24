# 🏡 Wittenberge Land & Village Plot Hunter
### 24/7 Autonomous Cloud Scraper & Groq AI Evidence Evaluator for **Iurii**

[![Scrape Every 4 Hours](https://github.com/BeagelDars/wittenberge-land-scraper/actions/workflows/scrape_every_4h.yml/badge.svg)](https://github.com/BeagelDars/wittenberge-land-scraper/actions/workflows/scrape_every_4h.yml)
[![Telegram Bot](https://img.shields.io/badge/Telegram-@Grundstuck__Wittenberge__bot-blue?logo=telegram)](https://t.me/Grundstuck_Wittenberge_bot)
[![Match Threshold](https://img.shields.io/badge/Strict%20Filter-%E2%89%A570%25%20Match-success)](#)
[![Evaluator](https://img.shields.io/badge/Groq%20AI-Zero--Hallucination%20Evidence-orange)](#)

---

## 🟢 Live System Status & Heartbeat

| Status Indicator | Metric | Value |
| :--- | :--- | :--- |
| 🟢 **Heartbeat** | Runner Schedule | Every 4 hours (`0 */4 * * *`) via GitHub Actions |
| ⏱️ **Last Cycle** | Executed at | `2026-09-24 23:14:04 UTC` |
| 🎯 **Target Region** | Search Area | **Wittenberge (19322) + 30 km radius** (Prignitz / Altmark) |
| 📐 **Target Area** | Plot Size | **1,000 – 5,000 m²** (Village plots & building land) |
| 🤖 **Telegram Alert** | Client Recipient | **Iurii (`1003559461`)** via [@Grundstuck_Wittenberge_bot](https://t.me/Grundstuck_Wittenberge_bot) |
| 📊 **Active Matches** | Score ≥ 70% | **3** verified listings |

---

## 🎯 High-Match Properties (≥ 70% Match Score)

> These properties strictly verified zero-hallucination evidence quotes for sale offer, property type, 30km radius, and 1,000-5,000 m² area.

| Match | Title | Price | Location | Area | Groq Evidence Quotes | Link |
| :---: | :--- | :---: | :--- | :---: | :--- | :---: |
| **100%** | [Neubaufläche in Top-Lage von Wittenberge...](https://www.kleinanzeigen.de/s-anzeige/neubauflaeche-in-top-lage-von-wittenberge/2969999189-207-7872) | `61.500 € VB` | 19322 Wittenberge Wittenberge (0 km) | 1080 m² | `Wir bieten Ihnen` / `Baugrundstücke` | [Direct Listing](https://www.kleinanzeigen.de/s-anzeige/neubauflaeche-in-top-lage-von-wittenberge/2969999189-207-7872) |
| **70%** | [ca. 1100 m² Freizeitgrundstück bei Pritzwalk ...](https://www.kleinanzeigen.de/s-anzeige/ca-1100-m-freizeitgrundstueck-bei-pritzwalk-eigentum/3455838482-207-20825) | `16.900 € VB` | 16928 Pritzwalk Wittenberge (0 km) | ca. 1100 m² | `Eigentum statt Pacht` / `Freizeitgrundstück` | [Direct Listing](https://www.kleinanzeigen.de/s-anzeige/ca-1100-m-freizeitgrundstueck-bei-pritzwalk-eigentum/3455838482-207-20825) |
| **95%** | [Baugrundstück in Kletzke bei Plattenburg – vi...](https://www.kleinanzeigen.de/s-anzeige/baugrundstueck-in-kletzke-bei-plattenburg-viel-platz-fuer-ihre-ideen/3490451538-207-25791) | `22.000 €` | 19339 Plattenburg Wittenberge (0 km) | knapp 1.000 m² | `Baugrundstück in Kletzke bei Plattenburg – viel Platz für Ihre Ideen` / `Baugrundstück` | [Direct Listing](https://www.kleinanzeigen.de/s-anzeige/baugrundstueck-in-kletzke-bei-plattenburg-viel-platz-fuer-ihre-ideen/3490451538-207-25791) |

---

## 🔍 Groq AI Audit Log (Last 15 Candidates Scanned)

| Ad ID | Verdict | Match % | Listing Title | AI Decision / Deduction Reason |
| :---: | :---: | :---: | :--- | :--- |
| `3494223925` | ❌ REJECT | **60%** | [Acker- und Grünland in Kyritz (Lkr....](https://www.kleinanzeigen.de/s-anzeige/acker-und-gruenland-in-kyritz-lkr-ostprignitz-ruppin-/3494223925-207-19105) | Размер превышает требуемый диапазон (65,0876 ha). |
| `3066367427` | ❌ REJECT | **35%** | [Bauland / Baugrundstück mit attrakt...](https://www.kleinanzeigen.de/s-anzeige/bauland-baugrundstueck-mit-attraktivem-weitblick-am-ortsrand/3066367427-207-21109) | Отсутствует подтверждение предложения продажи и размер не указан. |
| `2969999189` | ✅ MATCH | **100%** | [Neubaufläche in Top-Lage von Witten...](https://www.kleinanzeigen.de/s-anzeige/neubauflaeche-in-top-lage-von-wittenberge/2969999189-207-7872) | Approved (Passed all criteria) |
| `3480982463` | ❌ REJECT | **20%** | [Verkaufe 2,03 ha landw. Fläche & ba...](https://www.kleinanzeigen.de/s-anzeige/verkaufe-2-03-ha-landw-flaeche-baureifes-land-in-39596-arneburg-hv-/3480982463-207-23987) | Объект находится более чем в 30 км от Виттенберга и площадь превышает 5 000 м². |
| `3506718546` | ❌ REJECT | **0%** | [AUKTION - Wald an einer ehem. Bahns...](https://www.kleinanzeigen.de/s-anzeige/auktion-wald-an-einer-ehem-bahnstrecke-am-oestlichen-ortsrand-in-39539-nitzow/3506718546-207-7825) | Тип недвижимости не соответствует требованиям (лес), а местоположение более 30 км от Виттенберга. |
| `3522066538` | ❌ REJECT | **35%** | [Unbebautes Grundstück in Kyritz - A...](https://www.kleinanzeigen.de/s-anzeige/unbebautes-grundstueck-in-kyritz-attraktive-immobilienchance-ohne-provision/3522066538-207-19105) | Отсутствует подтверждение продажи и размер участка не указан. |
| `3522065923` | ❌ REJECT | **0%** | [Gartenlaube - Ihre Immobiliengelege...](https://www.kleinanzeigen.de/s-anzeige/gartenlaube-ihre-immobiliengelegenheit-provisionsfrei/3522065923-207-7825) | Не продажа, размер 31 м² (<1000), местоположение за пределами 30 км. |
| `3522064652` | ❌ REJECT | **35%** | [Land- und forstwirtschaftliches Gru...](https://www.kleinanzeigen.de/s-anzeige/land-und-forstwirtschaftliches-grundstueck-ihre-chance-auf-eine-attraktive-immobilie-ohne-provision/3522064652-207-7872) | Отсутствует размер участка. |
| `3522060361` | ❌ REJECT | **35%** | [unbebautes Grundstück - Interessant...](https://www.kleinanzeigen.de/s-anzeige/unbebautes-grundstueck-interessante-gelegenheit-fuer-kaeufer-ohne-provision/3522060361-207-20113) | Отсутствует размер участка. |
| `3419348192` | ❌ REJECT | **35%** | [Grundstück in 39606 Osterburg Provi...](https://www.kleinanzeigen.de/s-anzeige/grundstueck-in-39606-osterburg-provisionsfrei-schnell-sein-/3419348192-207-17235) | Отсутствует размер участка. |
| `2803065469` | ❌ REJECT | **35%** | [großzügiges Baugrundstück in attrak...](https://www.kleinanzeigen.de/s-anzeige/grosszuegiges-baugrundstueck-in-attraktiver/2803065469-207-7879) | Недостаточный процент совпадения (35%) |
| `3072861203` | ❌ REJECT | **65%** | [Dranse bei Wittstock , 4616 qm am e...](https://www.kleinanzeigen.de/s-anzeige/dranse-bei-wittstock-4616-qm-am-ehemaligen-bahnhof/3072861203-207-7879) | Недостаточный процент совпадения (65%) |
| `3521004822` | ❌ REJECT | **35%** | [6,51 ha Ackerland nahe Wittstock / ...](https://www.kleinanzeigen.de/s-anzeige/6-51-ha-ackerland-nahe-wittstock-ortsteil-schweinrich-zu-verkaufen/3521004822-207-7879) | Недостаточный процент совпадения (35%) |
| `3418616765` | ❌ REJECT | **35%** | [Grundstück in 39606 Osterburg Provi...](https://www.kleinanzeigen.de/s-anzeige/grundstueck-in-39606-osterburg-provisionsfrei-schnell-sein-/3418616765-207-17235) | Недостаточный процент совпадения (35%) |
| `3173930309` | ❌ REJECT | **10%** | [Attraktive Waldgrundstücke mit gute...](https://www.kleinanzeigen.de/s-anzeige/attraktive-waldgrundstuecke-mit-gutem-baumbestand-jagdgemeinschaft-wald-forstwirtschaft-/3173930309-207-25791) | Недостаточный процент совпадения (10%) |

---

## 🛡️ Zero-Hallucination Two-Step Architecture

```
Kleinanzeigen DOM Parser (Direct /s-anzeige/ URLs)
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Deterministic Python Pre-Filter                    │
│  • Instant rejection of Wanted Ads ("Gesuch", "Suche")      │
│  • Instant rejection of Leases ("Pacht", "Miete")           │
│  • Elimination of lawnmowers, tools, furniture, apartments  │
└──────────────────────────┬──────────────────────────────────┘
                           │ Pre-Filtered Candidates
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: Groq AI Evidence Evaluator (Strict Percentage)     │
│  • Offer for Sale: +35% (Wanted/Lease = 0% Reject)          │
│  • Plot in Village/Region: +25%                             │
│  • Location in 30km Radius: +20%                            │
│  • Size 1,000 - 5,000 m²: +20%                              │
│  • Verbatim Quote Verification: Must exist in source text   │
└──────────────────────────┬──────────────────────────────────┘
                           │ Match Score ≥ 70%
                           ▼
          Instant Telegram Alert to Iurii
            + Live Dashboard Update
```

---
*Auto-updated by GitHub Actions 24/7 Cloud Worker. Next run in ~4 hours.*
