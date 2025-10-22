import { ImageWithFallback } from './components/figma/ImageWithFallback';
import { Card, CardContent } from './components/ui/card';
import { Button } from './components/ui/button';
import { Badge } from './components/ui/badge';

export default function App() {
  const recommendations = [
    {
      id: 1,
      image: "https://images.unsplash.com/photo-1610123172763-1f587473048f?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxjb3p5JTIwc3R1ZGlvJTIwYXBhcnRtZW50fGVufDF8fHx8MTc2MDI2MDMzMXww&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral",
      title: "Cozy Studio in Downtown",
      beds: 1,
      baths: 1,
      sqft: 750,
      matchScore: 92
    },
    {
      id: 2,
      image: "https://images.unsplash.com/photo-1603072388139-565853396b38?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxtb2Rlcm4lMjBhcGFydG1lbnQlMjBiZWRyb29tfGVufDF8fHx8MTc2MDI5OTk5M3ww&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral",
      title: "Modern Loft with City Views",
      beds: 2,
      baths: 2,
      sqft: 1200,
      matchScore: 88
    },
    {
      id: 3,
      image: "https://images.unsplash.com/photo-1632077209523-e9dede9b6b31?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxicmlnaHQlMjBhcGFydG1lbnQlMjBsaXZpbmd8ZW58MXx8fHwxNzYwMjM3NDQ2fDA&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral",
      title: "Bright Corner Unit",
      beds: 1,
      baths: 1,
      sqft: 850,
      matchScore: 95
    },
    {
      id: 4,
      image: "https://images.unsplash.com/photo-1614622350812-96b09c78af77?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxtaW5pbWFsJTIwYXBhcnRtZW50JTIwaW50ZXJpb3J8ZW58MXx8fHwxNzYwMzE4MTgwfDA&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral",
      title: "Minimalist Suite",
      beds: 1,
      baths: 1,
      sqft: 680,
      matchScore: 85
    },
    {
      id: 5,
      image: "https://images.unsplash.com/photo-1552189864-e05b02af1697?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHx1cmJhbiUyMGFwYXJ0bWVudCUyMHJvb218ZW58MXx8fHwxNzYwMzE4MTgwfDA&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral",
      title: "Urban Living Space",
      beds: 2,
      baths: 1,
      sqft: 950,
      matchScore: 90
    },
    {
      id: 6,
      image: "https://images.unsplash.com/photo-1681684565407-01d2933ed16f?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxzcGFjaW91cyUyMGxvZnQlMjBhcGFydG1lbnR8ZW58MXx8fHwxNzYwMzE4MTgwfDA&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral",
      title: "Spacious Industrial Loft",
      beds: 3,
      baths: 2,
      sqft: 1500,
      matchScore: 87
    }
  ];

  return (
    <div className="min-h-screen bg-white">
      {/* Navigation */}
      <nav className="border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-6 sm:px-8 lg:px-12">
          <div className="flex items-center justify-between h-20">
            {/* Logo */}
            <div className="text-gray-900 tracking-tight">
              Padly
            </div>
            
            {/* Navigation Links */}
            <div className="hidden md:flex items-center gap-10">
              <a href="#" className="text-gray-600 hover:text-gray-900 transition-colors">
                Home
              </a>
              <a href="#" className="text-gray-600 hover:text-gray-900 transition-colors">
                Preferences
              </a>
              <a href="#" className="text-gray-600 hover:text-gray-900 transition-colors">
                Recommendations
              </a>
              <a href="#" className="text-gray-600 hover:text-gray-900 transition-colors">
                Account
              </a>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 sm:px-8 lg:px-12 py-16">
        {/* Header Section */}
        <div className="mb-16 text-center">
          <h1 className="text-gray-900 mb-4">
            Your perfect place awaits
          </h1>
          <p className="text-gray-500 max-w-2xl mx-auto">
            Here are your top matches based on your preferences
          </p>
        </div>

        {/* Recommendations Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {recommendations.map((recommendation) => (
            <Card 
              key={recommendation.id} 
              className="overflow-hidden border-gray-100 hover:shadow-xl transition-all duration-300 rounded-2xl"
            >
              {/* Image */}
              <div className="relative aspect-[4/3] overflow-hidden bg-gray-100">
                <ImageWithFallback
                  src={recommendation.image}
                  alt={recommendation.title}
                  className="w-full h-full object-cover transition-transform duration-500 hover:scale-105"
                />
                {/* Match Score Badge */}
                <Badge 
                  className="absolute top-4 right-4 bg-white/95 text-teal-600 hover:bg-white backdrop-blur-sm border-0 shadow-sm"
                >
                  Match: {recommendation.matchScore}%
                </Badge>
              </div>

              {/* Content */}
              <CardContent className="p-6">
                {/* Title */}
                <h3 className="text-gray-900 mb-3">
                  {recommendation.title}
                </h3>

                {/* Details */}
                <p className="text-gray-500 mb-6">
                  {recommendation.beds} Bed • {recommendation.baths} Bath • {recommendation.sqft} sq ft
                </p>

                {/* CTA Button */}
                <Button 
                  className="w-full bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-colors"
                >
                  View Details
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </main>
    </div>
  );
}
