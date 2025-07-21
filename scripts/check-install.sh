#!/bin/bash

echo "🔍 Vérification de l'installation - Whisper Service"
echo "=================================================="
echo ""

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Fonction pour afficher les résultats
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
    fi
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Vérifications système
echo "🔧 VÉRIFICATIONS SYSTÈME"
echo "========================"

# Docker
if command -v docker &> /dev/null; then
    print_result 0 "Docker installé"
    docker_version=$(docker --version | cut -d' ' -f3 | cut -d',' -f1)
    print_info "Version: $docker_version"
else
    print_result 1 "Docker non installé"
    print_warning "Installez Docker: https://docs.docker.com/get-docker/"
fi

# Docker Compose
if command -v docker-compose &> /dev/null; then
    print_result 0 "Docker Compose installé"
    compose_version=$(docker-compose --version | cut -d' ' -f3 | cut -d',' -f1)
    print_info "Version: $compose_version"
else
    print_result 1 "Docker Compose non installé"
    print_warning "Installez Docker Compose: https://docs.docker.com/compose/install/"
fi

# Python
if command -v python3 &> /dev/null; then
    print_result 0 "Python3 installé"
    python_version=$(python3 --version | cut -d' ' -f2)
    print_info "Version: $python_version"
else
    print_result 1 "Python3 non installé"
fi

# Node.js
if command -v node &> /dev/null; then
    print_result 0 "Node.js installé"
    node_version=$(node --version)
    print_info "Version: $node_version"
else
    print_result 1 "Node.js non installé"
    print_warning "Installez Node.js: https://nodejs.org/"
fi

# npm
if command -v npm &> /dev/null; then
    print_result 0 "npm installé"
    npm_version=$(npm --version)
    print_info "Version: $npm_version"
else
    print_result 1 "npm non installé"
fi

echo ""
echo "📁 VÉRIFICATIONS PROJET"
echo "======================="

# Fichiers essentiels
files=(
    "Dockerfile"
    "docker-compose.yml"
    "server.py"
    "requirements.txt"
    "package.json"
    "README.md"
)

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        print_result 0 "$file présent"
    else
        print_result 1 "$file manquant"
    fi
done

# Fichier de test
if [ -f "data/avatar_test_short.mp3" ]; then
    size=$(ls -lh data/avatar_test_short.mp3 | awk '{print $5}')
    print_result 0 "Fichier de test présent ($size)"
else
    print_result 1 "Fichier de test manquant"
    print_warning "Placez votre fichier audio dans data/avatar_test_short.mp3"
fi

echo ""
echo "🐳 VÉRIFICATIONS DOCKER"
echo "======================"

# Vérifier si les conteneurs sont en cours d'exécution
if docker-compose ps | grep -q "Up"; then
    print_result 0 "Services Docker en cours d'exécution"
    docker-compose ps
else
    print_result 1 "Services Docker non démarrés"
    print_info "Démarrez avec: npm start"
fi

echo ""
echo "🌐 VÉRIFICATIONS API"
echo "==================="

# Test de l'API si elle est accessible
if curl -f http://localhost:8080/health > /dev/null 2>&1; then
    print_result 0 "API accessible"
    
    # Test des modèles
    if curl -s http://localhost:8080/models | grep -q "ggml-base.bin"; then
        print_result 0 "Modèle base disponible"
    else
        print_result 1 "Modèle base non trouvé"
    fi
else
    print_result 1 "API non accessible"
    print_info "Démarrez le service: npm start"
fi

echo ""
echo "📊 RÉSUMÉ"
echo "=========="

# Compter les erreurs
errors=0
if ! command -v docker &> /dev/null; then ((errors++)); fi
if ! command -v docker-compose &> /dev/null; then ((errors++)); fi
if ! command -v node &> /dev/null; then ((errors++)); fi
if ! command -v npm &> /dev/null; then ((errors++)); fi
if [ ! -f "data/avatar_test_short.mp3" ]; then ((errors++)); fi

if [ $errors -eq 0 ]; then
    echo -e "${GREEN}🎉 Installation complète et fonctionnelle !${NC}"
    echo ""
    echo "💡 Prochaines étapes:"
    echo "   npm start          # Démarrer le service"
    echo "   npm run test-quick # Test rapide"
    echo "   npm run help       # Voir tous les scripts"
else
    echo -e "${YELLOW}⚠️  $errors problème(s) détecté(s)${NC}"
    echo ""
    echo "🔧 Solutions:"
    echo "   npm run help       # Voir les scripts disponibles"
    echo "   npm run setup      # Installation automatique"
fi 